from pathlib import Path

import pytest

from rate_card.sources.xai import XAI

FIXTURE = Path(__file__).parent / "fixtures" / "scrapers" / "xai.html"


@pytest.fixture()
def entries():
    scraper = XAI()
    scraper.use_fixture(str(FIXTURE))
    raw = scraper.fetch()
    return list(scraper.transform(raw))


def test_extract_returns_models(entries):
    assert len(entries) >= 4


def test_grok3_prices(entries):
    row = next(e for e in entries if e["model_id"] == "xai/grok-3")
    assert row["input_per_million"] == pytest.approx(3.0)
    assert row["output_per_million"] == pytest.approx(15.0)


def test_grok3_mini_prices(entries):
    row = next(e for e in entries if e["model_id"] == "xai/grok-3-mini")
    assert row["input_per_million"] == pytest.approx(0.3)
    assert row["output_per_million"] == pytest.approx(0.5)


def test_grok4_prices(entries):
    row = next(e for e in entries if e["model_id"] == "xai/grok-4-0709")
    assert row["input_per_million"] == pytest.approx(3.0)
    assert row["output_per_million"] == pytest.approx(15.0)


def test_cache_read_present(entries):
    row = next(e for e in entries if e["model_id"] == "xai/grok-3")
    assert "cache_read_per_million" in row
    assert row["cache_read_per_million"] == pytest.approx(0.75)


def test_provider_and_key(entries):
    row = next(e for e in entries if e["model_id"] == "xai/grok-3")
    assert row["provider"] == "xai"
    assert row["key"] == "xai:xai/grok-3"
    assert row["sources"] == ["xai-direct"]


def test_no_duplicates(entries):
    ids = [e["model_id"] for e in entries]
    assert len(ids) == len(set(ids))


def test_missing_rsc_block_returns_empty():
    # Page without the RSC pricing block emits no rows
    scraper = XAI()
    result = list(scraper.transform("<html><body>no pricing here</body></html>"))
    assert result == []
