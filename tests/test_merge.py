import pytest

from rate_card.merge import merge
from rate_card.types import PartialEntry


def _entry(
    key: str,
    input_price: float = 2.5,
    output_price: float = 10.0,
    source: str = "litellm",
    **extras: object,
) -> PartialEntry:
    e: PartialEntry = {
        "key": key,
        "provider": "openai",  # type: ignore[typeddict-item]
        "model_id": key.split(":")[-1],
        "mode": "chat",
        "input_per_million": input_price,
        "output_per_million": output_price,
        "context_window": 128000,
        "capabilities": [],
        "verified": "2026-05-02",
        "sources": [source],
    }
    for k, v in extras.items():
        e[k] = v  # type: ignore[literal-required]
    return e


def test_single_source_identity() -> None:
    entries = [_entry("openai:gpt-4o"), _entry("anthropic:claude-sonnet-4-5", input_price=3.0)]
    merged, divs = merge({"litellm": entries}, threshold=0.20)
    assert len(merged) == 2
    assert divs == []


def test_single_source_keys_preserved() -> None:
    entries = [_entry("openai:gpt-4o")]
    merged, _ = merge({"litellm": entries}, threshold=0.20)
    assert merged[0]["key"] == "openai:gpt-4o"
    assert merged[0]["input_per_million"] == pytest.approx(2.5)


def test_two_source_overlay_secondary_wins() -> None:
    primary = [_entry("openai:gpt-4o", input_price=2.5, context_window=128000)]
    secondary = [_entry("openai:gpt-4o", input_price=2.5, source="openai-direct")]
    # Add a field that only secondary knows about
    secondary[0]["max_output_tokens"] = 32768

    merged, _ = merge({"litellm": primary, "openai-direct": secondary}, threshold=0.20)
    assert len(merged) == 1
    assert merged[0].get("max_output_tokens") == 32768


def test_sources_union() -> None:
    primary = [_entry("openai:gpt-4o", source="litellm")]
    secondary = [_entry("openai:gpt-4o", source="openai-direct")]
    merged, _ = merge({"litellm": primary, "openai-direct": secondary}, threshold=0.20)
    assert set(merged[0]["sources"]) == {"litellm", "openai-direct"}


def test_divergence_detected_above_threshold() -> None:
    primary = [_entry("openai:gpt-4o", input_price=2.5)]
    # 2.5 * 1.25 = 3.125, which is exactly 25% above 2.5 (above 20% threshold)
    secondary = [_entry("openai:gpt-4o", input_price=3.125, source="openai-direct")]
    _, divs = merge({"litellm": primary, "openai-direct": secondary}, threshold=0.20)
    assert len(divs) == 1
    assert divs[0].field == "input_per_million"
    assert divs[0].secondary_source == "openai-direct"
    assert divs[0].delta_pct == pytest.approx(0.25)


def test_no_divergence_at_threshold_boundary() -> None:
    primary = [_entry("openai:gpt-4o", input_price=2.5)]
    # exactly 20% difference - not above threshold
    secondary = [_entry("openai:gpt-4o", input_price=3.0, source="openai-direct")]
    _, divs = merge({"litellm": primary, "openai-direct": secondary}, threshold=0.20)
    assert divs == []


def test_divergence_output_price() -> None:
    primary = [_entry("openai:gpt-4o", output_price=10.0)]
    secondary = [_entry("openai:gpt-4o", output_price=13.0, source="openai-direct")]
    _, divs = merge({"litellm": primary, "openai-direct": secondary}, threshold=0.20)
    assert any(d.field == "output_per_million" for d in divs)


def test_missing_in_secondary_keeps_primary() -> None:
    primary = [_entry("openai:gpt-4o"), _entry("openai:o1")]
    secondary = [_entry("openai:gpt-4o", source="openai-direct")]
    merged, _ = merge({"litellm": primary, "openai-direct": secondary}, threshold=0.20)
    keys = {e["key"] for e in merged}
    assert "openai:o1" in keys


def test_secondary_only_entry_added() -> None:
    primary = [_entry("openai:gpt-4o")]
    secondary = [_entry("openai:o1", source="openai-direct")]
    merged, _ = merge({"litellm": primary, "openai-direct": secondary}, threshold=0.20)
    assert len(merged) == 2


def test_divergence_zero_primary_skipped() -> None:
    primary = [_entry("openai:gpt-4o", **{"cache_read_per_million": 0.0})]  # type: ignore[arg-type]
    secondary = [_entry("openai:gpt-4o", source="openai-direct", **{"cache_read_per_million": 1.0})]  # type: ignore[arg-type]
    _, divs = merge({"litellm": primary, "openai-direct": secondary}, threshold=0.20)
    assert not any(d.field == "cache_read_per_million" for d in divs)


def test_empty_entries_returns_empty() -> None:
    merged, divs = merge({"litellm": []}, threshold=0.20)
    assert merged == []
    assert divs == []


def test_multiple_divergences_same_entry() -> None:
    primary = [_entry("openai:gpt-4o", input_price=2.5, output_price=10.0)]
    secondary = [_entry("openai:gpt-4o", input_price=4.0, output_price=16.0, source="other")]
    _, divs = merge({"litellm": primary, "other": secondary}, threshold=0.20)
    fields = {d.field for d in divs}
    assert "input_per_million" in fields
    assert "output_per_million" in fields


# ── modality_pricing deep-merge ────────────────────────────────────────────────


def test_modality_pricing_deep_merge() -> None:
    primary = [
        _entry("openai:gpt-realtime", modality_pricing={"audio": {"input_per_million": 32.0}})
    ]
    secondary = [
        _entry(
            "openai:gpt-realtime",
            source="openai-direct",
            modality_pricing={"image": {"input_per_million": 5.0}},
        )
    ]
    merged, _ = merge({"litellm": primary, "openai-direct": secondary}, threshold=0.20)
    mp = merged[0].get("modality_pricing", {})
    assert "audio" in mp
    assert "image" in mp
    assert mp["audio"]["input_per_million"] == pytest.approx(32.0)
    assert mp["image"]["input_per_million"] == pytest.approx(5.0)


def test_modality_pricing_secondary_overwrites_same_key() -> None:
    primary = [
        _entry("openai:gpt-realtime", modality_pricing={"audio": {"input_per_million": 32.0}})
    ]
    secondary = [
        _entry(
            "openai:gpt-realtime",
            source="openai-direct",
            modality_pricing={"audio": {"input_per_million": 20.0}},
        )
    ]
    merged, _ = merge({"litellm": primary, "openai-direct": secondary}, threshold=0.20)
    mp = merged[0].get("modality_pricing", {})
    assert mp["audio"]["input_per_million"] == pytest.approx(20.0)


def test_modality_pricing_primary_only_preserved() -> None:
    primary = [
        _entry("openai:gpt-realtime", modality_pricing={"audio": {"input_per_million": 32.0}})
    ]
    secondary = [_entry("openai:gpt-realtime", source="openai-direct")]
    merged, _ = merge({"litellm": primary, "openai-direct": secondary}, threshold=0.20)
    mp = merged[0].get("modality_pricing", {})
    assert "audio" in mp
