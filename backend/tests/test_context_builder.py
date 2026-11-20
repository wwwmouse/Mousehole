from __future__ import annotations

from types import SimpleNamespace

from app.modules.context import builder


def _workspace(override: int | None = None) -> SimpleNamespace:
    return SimpleNamespace(context_budget_tokens=override)


def test_compute_budget_from_model_window_and_override() -> None:
    deepseek_budget = builder.compute_budget(
        _workspace(), "deepseek", "deepseek-flash", max_tokens=4096
    )
    assert deepseek_budget > 100_000  # 1M window minus reserves

    unknown_budget = builder.compute_budget(
        _workspace(), "unknown", "some-model", max_tokens=2048
    )
    assert unknown_budget == builder.DEFAULT_WINDOW - 2048 - builder.OVERHEAD_RESERVE

    overridden = builder.compute_budget(
        _workspace(8000), "deepseek", "deepseek-flash", max_tokens=1024
    )
    assert overridden == 8000


def test_estimate_tokens_is_deterministic() -> None:
    assert builder.estimate_tokens("a" * 400) == 100
    assert builder.estimate_tokens("") == 1


def _items(count: int, size: int):
    items = []
    for index in range(count):
        fake_file = SimpleNamespace(filename=f"f{index}.md")
        items.append(
            builder.FileText(
                file=fake_file,
                source_type="project_inherited",
                text="x" * size,
            )
        )
    return items


def test_plan_context_direct_when_it_fits() -> None:
    items = _items(2, 400)  # ~200 tokens + overhead
    plan = builder.plan_context(items, budget=10_000)
    assert plan.mode == "direct"
    assert "f0.md" in plan.context_text
    assert plan.batches == []


def test_plan_context_splits_when_over_budget() -> None:
    items = _items(5, 20_000)  # ~5000 tokens each
    plan = builder.plan_context(items, budget=12_000)
    assert plan.mode == "summarized"
    assert len(plan.batches) >= 2
    # every file appears in exactly one batch
    batched = [item for batch in plan.batches for item in batch]
    assert len(batched) == len(items)
