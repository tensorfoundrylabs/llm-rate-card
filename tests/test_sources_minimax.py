from pathlib import Path

import pytest

from rate_card.sources.minimax import MiniMax

FIXTURE = Path(__file__).parent / "fixtures" / "scrapers" / "minimax.html"


@pytest.fixture()
def entries():
    scraper = MiniMax()
    scraper.use_fixture(str(FIXTURE))
    raw = scraper.fetch()
    return list(scraper.transform(raw))


def test_extract_returns_models(entries):
    assert len(entries) >= 2


def test_model_ids_present(entries):
    ids = {e["model_id"] for e in entries}
    assert "MiniMax-M2.7" in ids
    assert "MiniMax-M2.5" in ids


def test_m27_prices(entries):
    row = next(e for e in entries if e["model_id"] == "MiniMax-M2.7")
    assert row["input_per_million"] == pytest.approx(0.3)
    assert row["output_per_million"] == pytest.approx(1.2)


def test_m25_prices(entries):
    row = next(e for e in entries if e["model_id"] == "MiniMax-M2.5")
    assert row["input_per_million"] == pytest.approx(0.3)
    assert row["output_per_million"] == pytest.approx(1.2)


def test_cache_pricing_present(entries):
    row = next(e for e in entries if e["model_id"] == "MiniMax-M2.7")
    assert "cache_read_per_million" in row
    assert row["cache_read_per_million"] == pytest.approx(0.06)
    assert "cache_write_per_million" in row
    assert row["cache_write_per_million"] == pytest.approx(0.375)


def test_provider_and_key(entries):
    row = next(e for e in entries if e["model_id"] == "MiniMax-M2.7")
    assert row["provider"] == "minimax"
    assert row["key"] == "minimax:MiniMax-M2.7"
    assert row["sources"] == ["minimax-direct"]


def test_non_text_tables_excluded(entries):
    # Video and audio models should not appear - they lack Input/Output token columns
    ids = {e["model_id"] for e in entries}
    assert "MiniMax-Hailuo-2.3-Fast" not in ids
    assert "Music-2.6" not in ids


def test_malformed_price_row_excluded():
    html = """
    <table>
      <thead><tr><th>Model</th><th>Input</th><th>Output</th></tr></thead>
      <tbody>
        <tr><td>MM-X</td><td>not-a-price</td><td>also-not</td></tr>
      </tbody>
    </table>
    """
    scraper = MiniMax()
    result = list(scraper.transform(html))
    assert all(e["model_id"] != "MM-X" for e in result)
