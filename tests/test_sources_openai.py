from pathlib import Path

import pytest

from rate_card.sources.openai import OpenAI

FIXTURE = Path(__file__).parent / "fixtures" / "scrapers" / "openai.html"


@pytest.fixture()
def entries():
    scraper = OpenAI()
    scraper.use_fixture(str(FIXTURE))
    raw = scraper.fetch()
    return list(scraper.transform(raw))


def test_extract_returns_models(entries):
    assert len(entries) >= 5


def test_gpt55_prices(entries):
    row = next(e for e in entries if e["model_id"] == "gpt-5.5")
    assert row["input_per_million"] == pytest.approx(5.0)
    assert row["output_per_million"] == pytest.approx(30.0)


def test_gpt54_prices(entries):
    row = next(e for e in entries if e["model_id"] == "gpt-5.4")
    assert row["input_per_million"] == pytest.approx(2.5)
    assert row["output_per_million"] == pytest.approx(15.0)


def test_gpt54_mini_prices(entries):
    row = next(e for e in entries if e["model_id"] == "gpt-5.4-mini")
    assert row["input_per_million"] == pytest.approx(0.75)
    assert row["output_per_million"] == pytest.approx(4.5)


def test_cache_read_present(entries):
    row = next(e for e in entries if e["model_id"] == "gpt-5.5")
    assert "cache_read_per_million" in row
    assert row["cache_read_per_million"] == pytest.approx(0.5)


def test_long_context_tier_present(entries):
    row = next(e for e in entries if e["model_id"] == "gpt-5.5")
    assert "pricing_tiers" in row
    tier = row["pricing_tiers"][0]
    assert tier["above_input_tokens"] == 200_000
    assert tier["input_per_million"] == pytest.approx(10.0)
    assert tier["output_per_million"] == pytest.approx(45.0)


def test_model_without_long_context_has_no_tier(entries):
    row = next(e for e in entries if e["model_id"] == "gpt-5.4-mini")
    assert "pricing_tiers" not in row


def test_provider_and_key(entries):
    row = next(e for e in entries if e["model_id"] == "gpt-5.5")
    assert row["provider"] == "openai"
    assert row["key"] == "openai:gpt-5.5"
    assert row["sources"] == ["openai-direct"]


def test_no_duplicates(entries):
    ids = [e["model_id"] for e in entries]
    assert len(ids) == len(set(ids))


def test_fine_tuning_rows_excluded(entries):
    # Fine-tuning table rows should not appear (they have a "Training" column)
    ids = {e["model_id"] for e in entries}
    assert "o4-mini-2025-04-16with data sharing" not in ids


def test_malformed_price_row_excluded():
    html = """
    <table>
      <thead><tr><th></th><th>Short context</th><th>Long context</th>
        <tr><th>Model</th><th>Input</th><th>Cached input</th><th>Output</th>
            <th>Input</th><th>Cached input</th><th>Output</th></tr>
      </thead>
      <tbody>
        <tr><td>gpt-test</td><td>not-a-price</td><td>-</td><td>also-not</td><td>-</td><td>-</td><td>-</td></tr>
      </tbody>
    </table>
    """
    scraper = OpenAI()
    result = list(scraper.transform(html))
    assert all(e["model_id"] != "gpt-test" for e in result)
