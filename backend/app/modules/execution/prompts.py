from __future__ import annotations

SUMMARY_SYSTEM = (
    "你是 mousehole 的文档摘要助手。请忠实提炼给定资料的关键信息，"
    "保留事实、数字、结论与来源文件名；不要编造资料中没有的内容。"
)


def summary_messages(filename: str, text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SUMMARY_SYSTEM},
        {
            "role": "user",
            "content": (
                f"请为文件「{filename}」生成一份简洁摘要（不超过 500 字），"
                f"保留关键事实与结论：\n\n{text}"
            ),
        },
    ]
