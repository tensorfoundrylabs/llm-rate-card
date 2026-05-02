from rate_card.changelog import ChangeSummary, format_release_notes, format_summary, summarise


def test_format_release_notes_contains_compare_url() -> None:
    result = format_release_notes("tensorfoundrylabs/llm-rate-card", "2026.04.01", "2026.05.02")
    assert "tensorfoundrylabs/llm-rate-card" in result
    assert "2026.04.01...2026.05.02" in result
    assert "https://github.com/" in result


def test_format_release_notes_is_one_line() -> None:
    result = format_release_notes("tensorfoundrylabs/llm-rate-card", "2026.04.01", "2026.05.02")
    assert "\n" not in result


def test_format_release_notes_is_markdown_link() -> None:
    result = format_release_notes("tensorfoundrylabs/llm-rate-card", "2026.04.01", "2026.05.02")
    assert "[" in result
    assert "](" in result


# --- summarise ---


def _entry(key: str, **overrides: object) -> dict:
    base: dict = {
        "key": key,
        "input_per_million": 1.0,
        "output_per_million": 2.0,
        "capabilities": ["streaming"],
        "context_window": 8192,
    }
    base.update(overrides)
    return base


def _doc(*entries: dict) -> dict:
    return {"models": list(entries)}


def test_summarise_previous_none_all_added() -> None:
    curr = _doc(_entry("openai:gpt-4o"), _entry("anthropic:claude-3"))
    result = summarise(None, curr)
    assert sorted(result.added) == ["anthropic:claude-3", "openai:gpt-4o"]
    assert result.removed == []
    assert result.repriced == []
    assert result.updated == []


def test_summarise_empty_previous_models_all_added() -> None:
    prev = {"models": []}
    curr = _doc(_entry("openai:gpt-4o"))
    result = summarise(prev, curr)
    assert result.added == ["openai:gpt-4o"]
    assert result.removed == []


def test_summarise_identical_docs_all_empty() -> None:
    entry = _entry("openai:gpt-4o")
    result = summarise(_doc(entry), _doc(entry))
    assert result.added == []
    assert result.removed == []
    assert result.repriced == []
    assert result.updated == []


def test_summarise_key_only_in_previous_is_removed() -> None:
    prev = _doc(_entry("openai:gpt-3.5-turbo"), _entry("openai:gpt-4o"))
    curr = _doc(_entry("openai:gpt-4o"))
    result = summarise(prev, curr)
    assert result.removed == ["openai:gpt-3.5-turbo"]
    assert result.added == []


def test_summarise_key_only_in_current_is_added() -> None:
    prev = _doc(_entry("openai:gpt-4o"))
    curr = _doc(_entry("openai:gpt-4o"), _entry("openai:gpt-5"))
    result = summarise(prev, curr)
    assert result.added == ["openai:gpt-5"]
    assert result.removed == []


def test_summarise_input_price_change_is_repriced() -> None:
    prev = _doc(_entry("openai:gpt-4o", input_per_million=1.0))
    curr = _doc(_entry("openai:gpt-4o", input_per_million=2.5))
    result = summarise(prev, curr)
    assert result.repriced == ["openai:gpt-4o"]
    assert result.updated == []


def test_summarise_pricing_tier_price_change_is_repriced() -> None:
    tier_prev = {"above_input_tokens": 0, "output_per_million": 3.0}
    tier_curr = {"above_input_tokens": 0, "output_per_million": 5.0}
    prev = _doc(_entry("openai:gpt-4o", pricing_tiers=[tier_prev]))
    curr = _doc(_entry("openai:gpt-4o", pricing_tiers=[tier_curr]))
    result = summarise(prev, curr)
    assert result.repriced == ["openai:gpt-4o"]


def test_summarise_capability_added_no_price_change_is_updated() -> None:
    prev = _doc(_entry("openai:gpt-4o", capabilities=["streaming"]))
    curr = _doc(_entry("openai:gpt-4o", capabilities=["streaming", "vision"]))
    result = summarise(prev, curr)
    assert result.updated == ["openai:gpt-4o"]
    assert result.repriced == []


def test_summarise_verified_change_only_is_no_category() -> None:
    prev = _doc(_entry("openai:gpt-4o", verified="2026-01-01"))
    curr = _doc(_entry("openai:gpt-4o", verified="2026-05-01"))
    result = summarise(prev, curr)
    assert result.added == []
    assert result.removed == []
    assert result.repriced == []
    assert result.updated == []


def test_summarise_price_and_capability_change_repriced_wins() -> None:
    prev = _doc(_entry("openai:gpt-4o", input_per_million=1.0, capabilities=["streaming"]))
    curr = _doc(
        _entry("openai:gpt-4o", input_per_million=2.0, capabilities=["streaming", "vision"])
    )
    result = summarise(prev, curr)
    assert result.repriced == ["openai:gpt-4o"]
    assert result.updated == []


def test_summarise_missing_optional_price_field_is_repriced() -> None:
    prev = _doc(_entry("openai:gpt-4o", cache_read_per_million=0.3))
    curr = _doc(_entry("openai:gpt-4o"))
    result = summarise(prev, curr)
    assert result.repriced == ["openai:gpt-4o"]


# --- format_summary ---


def test_format_summary_all_four_populated() -> None:
    summary = ChangeSummary(
        added=["anthropic:claude-haiku-5", "openai:gpt-6"],
        removed=["openai:gpt-3.5-turbo"],
        repriced=[
            "anthropic:claude-3",
            "openai:gpt-4",
            "openai:gpt-4o",
            "openai:gpt-4o-mini",
            "openai:o1",
        ],
        updated=["anthropic:claude-sonnet-4", "openai:gpt-4-turbo", "openai:o3"],
    )
    text = format_summary(summary)

    assert "2 added" in text
    assert "1 removed" in text
    assert "5 repriced" in text
    assert "3 updated" in text

    assert "`anthropic:claude-haiku-5`" in text
    assert "`openai:gpt-6`" in text
    assert "`openai:gpt-3.5-turbo`" in text

    for key in summary.repriced + summary.updated:
        assert f"`{key}`" not in text


def test_format_summary_only_added_no_other_sections() -> None:
    summary = ChangeSummary(added=["openai:gpt-5"])
    text = format_summary(summary)
    assert "1 added" in text
    assert "removed" not in text
    assert "repriced" not in text
    assert "updated" not in text
    assert "0" not in text
    assert "`openai:gpt-5`" in text


def test_format_summary_empty_returns_no_changes() -> None:
    assert format_summary(ChangeSummary()) == "No changes."
