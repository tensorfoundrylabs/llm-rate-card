from rate_card.changelog import format_release_notes


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
