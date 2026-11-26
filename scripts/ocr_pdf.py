#!/usr/bin/env python
"""PDF OCR CLI：路由检测 + 文本层 / VLM OCR。

示例（在仓库根目录运行）：
    python scripts/ocr_pdf.py "D:\\docs\\学生手册.pdf" --inspect-only
    python scripts/ocr_pdf.py "D:\\docs\\学生手册.pdf" --limit 5 --dpi 200
    python scripts/ocr_pdf.py "D:\\docs\\学生手册.pdf" --format markdown

本地 VLM 默认使用 Ollama 的 OpenAI 兼容接口：
    OCR_VLM_BASE_URL=http://127.0.0.1:11434/v1
    OCR_VLM_MODEL=qwen3-vl:4b
    OCR_VLM_API_KEY=ollama
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.modules.document.ocr_service import process_pdf  # noqa: E402
from app.modules.document.pdf_router import inspect_pdf  # noqa: E402
from app.modules.document.vlm_ocr import (  # noqa: E402
    VlmOcrClient,
    VlmOcrConfig,
)
from app.shared.exceptions import AppError  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PDF 路由 + OCR 工具")
    parser.add_argument("input", type=Path, help="输入 PDF 路径")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="输出文件；不填则生成 <input>.ocr.json/.md",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="输出格式（默认 json）",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=70.0,
        help="图像覆盖率阈值（0–100，默认 70）",
    )
    parser.add_argument("--dpi", type=int, default=200, help="OCR 渲染 DPI")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="只处理前 N 页（用于抽样测试）",
    )
    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help="只输出路由统计，不执行 OCR/文本提取",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv(
            "OCR_VLM_BASE_URL", "http://127.0.0.1:11434/v1"
        ),
        help="OpenAI 兼容 VLM 地址",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OCR_VLM_MODEL", "qwen3-vl:4b"),
        help="VLM 模型名",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("OCR_VLM_API_KEY", "ollama"),
        help="VLM API Key（Ollama 可用占位值 ollama）",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("OCR_VLM_TIMEOUT_SECONDS", "180")),
        help="单页 VLM 超时秒数",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="不打印逐页进度",
    )
    return parser


def _default_output(input_path: Path, fmt: str) -> Path:
    suffix = ".ocr.md" if fmt == "markdown" else ".ocr.json"
    return input_path.with_name(input_path.name + suffix)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    path: Path = args.input
    if not path.is_file():
        print(f"输入文件不存在：{path}", file=sys.stderr)
        return 2

    data = path.read_bytes()
    try:
        if args.inspect_only:
            inspection = inspect_pdf(data, threshold=args.threshold)
            payload = {
                "filename": path.name,
                "page_count": inspection.page_count,
                "image_coverage": inspection.image_coverage,
                "text_chars": inspection.text_chars,
                "threshold": inspection.threshold,
                "route": inspection.route,
                "pages": [
                    {
                        "page_no": page.page_no,
                        "image_coverage": round(page.image_coverage, 2),
                        "text_chars": page.text_chars,
                        "route": page.route,
                    }
                    for page in inspection.pages
                ],
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        config = VlmOcrConfig(
            base_url=args.base_url,
            model=args.model,
            api_key=args.api_key,
            timeout_seconds=args.timeout,
        )
        client = VlmOcrClient(config)

        def progress(page_no: int, total: int) -> None:
            if not args.quiet:
                print(
                    f"\r第 {page_no}/{total} 页…",
                    end="",
                    file=sys.stderr,
                    flush=True,
                )

        try:
            result = process_pdf(
                data,
                filename=path.name,
                threshold=args.threshold,
                dpi=args.dpi,
                limit=args.limit,
                client=client,
                progress=progress,
            )
        finally:
            client.close()
            if not args.quiet:
                print("\r" + " " * 40 + "\r", end="", file=sys.stderr)

        output = args.output or _default_output(path, args.format)
        if args.format == "markdown":
            output.write_text(
                result.to_markdown() + "\n", encoding="utf-8"
            )
        else:
            output.write_text(
                json.dumps(
                    result.to_dict(), ensure_ascii=False, indent=2
                )
                + "\n",
                encoding="utf-8",
            )
        print(
            f"完成：route={result.route}，页数={result.processed_pages}/"
            f"{result.page_count}，输出={output}"
        )
        return 0
    except AppError as exc:
        print(f"错误：{exc.message}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - CLI 顶层兜底
        print(f"失败：{exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
