import textwrap
from pathlib import Path

from rate_card.filter import apply_whitelist, load_whitelist
from rate_card.types import PartialEntry


def _entry(key: str, provider: str = "openai", model_id: str = "") -> PartialEntry:
    return {
        "key": key,
        "provider": provider,  # type: ignore[typeddict-item]
        "model_id": model_id or key.split(":")[-1],
        "mode": "chat",
        "input_per_million": 2.5,
        "output_per_million": 10.0,
        "context_window": 128000,
        "capabilities": [],
        "verified": "2026-05-02",
        "sources": ["litellm"],
    }


def test_load_whitelist(tmp_path: Path) -> None:
    p = tmp_path / "whitelist.yaml"
    p.write_text(
        textwrap.dedent("""
        openai:
          - gpt-4o
          - o1
        anthropic:
          - claude-sonnet-4-5
    """)
    )
    wl = load_whitelist(p)
    assert wl["openai"] == ["gpt-4o", "o1"]
    assert wl["anthropic"] == ["claude-sonnet-4-5"]


def test_apply_whitelist_keeps_matching() -> None:
    entries = [_entry("openai:gpt-4o"), _entry("openai:o1"), _entry("openai:gpt-4-turbo")]
    whitelist = {"openai": ["gpt-4o", "o1"]}
    kept, _ = apply_whitelist(entries, whitelist)
    assert len(kept) == 2
    assert {e["key"] for e in kept} == {"openai:gpt-4o", "openai:o1"}


def test_apply_whitelist_drops_non_whitelisted() -> None:
    entries = [_entry("openai:gpt-4o"), _entry("openai:gpt-4-turbo")]
    whitelist = {"openai": ["gpt-4o"]}
    kept, _ = apply_whitelist(entries, whitelist)
    assert not any(e["key"] == "openai:gpt-4-turbo" for e in kept)


def test_apply_whitelist_reports_missing() -> None:
    entries = [_entry("openai:gpt-4o")]
    whitelist = {"openai": ["gpt-4o", "o1"]}
    _, missing = apply_whitelist(entries, whitelist)
    assert "openai:o1" in missing


def test_apply_whitelist_no_missing_when_all_present() -> None:
    entries = [_entry("openai:gpt-4o"), _entry("openai:o1")]
    whitelist = {"openai": ["gpt-4o", "o1"]}
    _, missing = apply_whitelist(entries, whitelist)
    assert missing == []


def test_apply_whitelist_empty_entries() -> None:
    whitelist = {"openai": ["gpt-4o"]}
    kept, missing = apply_whitelist([], whitelist)
    assert kept == []
    assert "openai:gpt-4o" in missing


def test_apply_whitelist_empty_whitelist() -> None:
    entries = [_entry("openai:gpt-4o")]
    kept, missing = apply_whitelist(entries, {})
    assert kept == []
    assert missing == []


def test_apply_whitelist_cross_provider() -> None:
    entries = [
        _entry("openai:gpt-4o", "openai"),
        _entry("anthropic:claude-sonnet-4-5", "anthropic"),
        _entry("gemini:gemini-2.0-flash", "gemini"),
    ]
    whitelist = {"openai": ["gpt-4o"], "anthropic": ["claude-sonnet-4-5"]}
    kept, _ = apply_whitelist(entries, whitelist)
    assert len(kept) == 2
    assert not any(e["key"] == "gemini:gemini-2.0-flash" for e in kept)
