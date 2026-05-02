from collections.abc import Iterable

import pytest

from rate_card.sources._scraper import BaseScraper, ScrapedRow
from rate_card.types import PricingTier


class _StubScraper(BaseScraper):
    name = "stub"
    provider = "openai"
    url = "https://example.com/pricing"

    def __init__(self, rows: list[ScrapedRow], **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._rows = rows

    def _extract(self, raw: str) -> Iterable[ScrapedRow]:
        return self._rows


def _make_scraper(*rows: ScrapedRow) -> _StubScraper:
    return _StubScraper(list(rows))


# ── key, provider, sources, source_url ──────────────────────────────────────


def test_row_to_entry_sets_key() -> None:
    scraper = _make_scraper(
        {"model_id": "gpt-4o", "input_per_million": 2.5, "output_per_million": 10.0}
    )
    entries = list(scraper.transform(""))
    assert entries[0]["key"] == "openai:gpt-4o"


def test_row_to_entry_sets_provider() -> None:
    scraper = _make_scraper(
        {"model_id": "gpt-4o", "input_per_million": 2.5, "output_per_million": 10.0}
    )
    entries = list(scraper.transform(""))
    assert entries[0]["provider"] == "openai"


def test_row_to_entry_sets_model_id() -> None:
    scraper = _make_scraper(
        {"model_id": "gpt-4o", "input_per_million": 2.5, "output_per_million": 10.0}
    )
    entries = list(scraper.transform(""))
    assert entries[0]["model_id"] == "gpt-4o"


def test_row_to_entry_sets_sources() -> None:
    scraper = _make_scraper(
        {"model_id": "gpt-4o", "input_per_million": 2.5, "output_per_million": 10.0}
    )
    entries = list(scraper.transform(""))
    assert entries[0]["sources"] == ["stub"]


def test_row_to_entry_sets_source_url() -> None:
    scraper = _make_scraper(
        {"model_id": "gpt-4o", "input_per_million": 2.5, "output_per_million": 10.0}
    )
    entries = list(scraper.transform(""))
    assert entries[0]["source_url"] == "https://example.com/pricing"


# ── rounding applied to numeric fields ────────────────────────────────────────


def test_row_to_entry_rounds_input() -> None:
    scraper = _make_scraper(
        {"model_id": "m", "input_per_million": 2.5000001, "output_per_million": 10.0}
    )
    entries = list(scraper.transform(""))
    assert entries[0]["input_per_million"] == pytest.approx(2.5)


def test_row_to_entry_rounds_cache_read() -> None:
    scraper = _make_scraper(
        {
            "model_id": "m",
            "input_per_million": 1.0,
            "output_per_million": 4.0,
            "cache_read_per_million": 0.30000004,
        }
    )
    entries = list(scraper.transform(""))
    assert entries[0]["cache_read_per_million"] == pytest.approx(0.3)


def test_row_to_entry_cache_none_preserved() -> None:
    scraper = _make_scraper(
        {
            "model_id": "m",
            "input_per_million": 1.0,
            "output_per_million": 4.0,
            "cache_read_per_million": None,
        }
    )
    entries = list(scraper.transform(""))
    assert entries[0]["cache_read_per_million"] is None


def test_row_to_entry_reasoning_rounded() -> None:
    scraper = _make_scraper(
        {
            "model_id": "m",
            "input_per_million": 1.0,
            "output_per_million": 4.0,
            "reasoning_per_million": 8.0,
        }
    )
    entries = list(scraper.transform(""))
    assert entries[0]["reasoning_per_million"] == pytest.approx(8.0)


# ── pricing_tiers carried through ─────────────────────────────────────────────


def test_row_to_entry_carries_pricing_tiers() -> None:
    tiers: list[PricingTier] = [
        {"above_input_tokens": 200_000, "input_per_million": 6.0, "output_per_million": 22.5}
    ]
    scraper = _make_scraper(
        {
            "model_id": "claude",
            "input_per_million": 3.0,
            "output_per_million": 15.0,
            "pricing_tiers": tiers,
        }
    )
    entries = list(scraper.transform(""))
    assert entries[0]["pricing_tiers"] == tiers


# ── missing optional fields produce minimal entries ────────────────────────────


def test_row_to_entry_minimal_row() -> None:
    scraper = _make_scraper({"model_id": "bare"})
    entries = list(scraper.transform(""))
    assert entries[0]["key"] == "openai:bare"
    assert "input_per_million" not in entries[0]
    assert "output_per_million" not in entries[0]
    assert "pricing_tiers" not in entries[0]


# ── mode/capabilities NOT set by scraper ──────────────────────────────────────


def test_row_to_entry_does_not_set_mode() -> None:
    scraper = _make_scraper({"model_id": "m", "input_per_million": 1.0, "output_per_million": 2.0})
    entries = list(scraper.transform(""))
    assert "mode" not in entries[0]


def test_row_to_entry_does_not_set_capabilities() -> None:
    scraper = _make_scraper({"model_id": "m", "input_per_million": 1.0, "output_per_million": 2.0})
    entries = list(scraper.transform(""))
    assert "capabilities" not in entries[0]


# ── multiple rows ──────────────────────────────────────────────────────────────


def test_transform_yields_multiple_rows() -> None:
    scraper = _make_scraper(
        {"model_id": "a", "input_per_million": 1.0, "output_per_million": 2.0},
        {"model_id": "b", "input_per_million": 3.0, "output_per_million": 6.0},
    )
    entries = list(scraper.transform(""))
    assert len(entries) == 2
    assert entries[0]["key"] == "openai:a"
    assert entries[1]["key"] == "openai:b"


# ── defaults ──────────────────────────────────────────────────────────────────


def test_scraper_role_defaults_to_secondary() -> None:
    assert _StubScraper.role == "secondary"


def test_scraper_enabled_default() -> None:
    scraper = _make_scraper()
    assert scraper.enabled is True


# ── use_fixture ───────────────────────────────────────────────────────────────


def test_use_fixture_sets_fixture_path() -> None:
    scraper = _make_scraper()
    scraper.use_fixture("/tmp/fixture.html")
    assert scraper._fixture_path == "/tmp/fixture.html"


# ── _extract not implemented on base ──────────────────────────────────────────


def test_base_extract_raises_not_implemented() -> None:
    base = BaseScraper.__new__(BaseScraper)
    with pytest.raises(NotImplementedError):
        list(base._extract(""))
