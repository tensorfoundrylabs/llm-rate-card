from pathlib import Path

import pytest

from rate_card.sources.anthropic import Anthropic

FIXTURE = Path(__file__).parent / "fixtures" / "scrapers" / "anthropic.html"


@pytest.fixture()
def entries():
    scraper = Anthropic()
    scraper.use_fixture(str(FIXTURE))
    raw = scraper.fetch()
    return list(scraper.transform(raw))


def test_extract_returns_models(entries):
    assert len(entries) >= 3


def test_model_ids_present(entries):
    ids = {e["model_id"] for e in entries}
    assert "claude-opus-4-7" in ids
    assert "claude-sonnet-4-6" in ids
    assert "claude-haiku-4-5" in ids


def test_opus_prices(entries):
    row = next(e for e in entries if e["model_id"] == "claude-opus-4-7")
    assert row["input_per_million"] == pytest.approx(5.0)
    assert row["output_per_million"] == pytest.approx(25.0)


def test_sonnet_prices(entries):
    row = next(e for e in entries if e["model_id"] == "claude-sonnet-4-6")
    assert row["input_per_million"] == pytest.approx(3.0)
    assert row["output_per_million"] == pytest.approx(15.0)


def test_haiku_prices(entries):
    row = next(e for e in entries if e["model_id"] == "claude-haiku-4-5")
    assert row["input_per_million"] == pytest.approx(1.0)
    assert row["output_per_million"] == pytest.approx(5.0)


def test_provider_and_key(entries):
    row = next(e for e in entries if e["model_id"] == "claude-sonnet-4-6")
    assert row["provider"] == "anthropic"
    assert row["key"] == "anthropic:claude-sonnet-4-6"
    assert row["sources"] == ["anthropic-direct"]


def test_missing_pricing_row_returns_empty():
    # Table without a Pricing row should produce no entries
    html = """
    <table>
      <thead><tr><th>Feature</th><th>Model A</th></tr></thead>
      <tbody>
        <tr><td>Claude API alias</td><td>claude-test</td></tr>
        <tr><td>Description</td><td>A test model</td></tr>
      </tbody>
    </table>
    """
    scraper = Anthropic()
    result = list(scraper.transform(html))
    assert result == []


def test_malformed_price_cell_excluded():
    html = """
    <table>
      <thead><tr><th>Feature</th><th>Model A</th></tr></thead>
      <tbody>
        <tr><td>Claude API alias</td><td>claude-test</td></tr>
        <tr><td>Pricing1</td><td>not-a-price</td></tr>
      </tbody>
    </table>
    """
    scraper = Anthropic()
    result = list(scraper.transform(html))
    assert all(e["model_id"] != "claude-test" for e in result)
