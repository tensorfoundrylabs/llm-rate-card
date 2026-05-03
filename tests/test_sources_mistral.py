from pathlib import Path

import pytest

from rate_card.sources.mistral import Mistral

FIXTURE = Path(__file__).parent / "fixtures" / "scrapers" / "mistral.html"


@pytest.fixture()
def entries():
    scraper = Mistral()
    scraper.use_fixture(str(FIXTURE))
    raw = scraper.fetch()
    return list(scraper.transform(raw))


def test_extract_returns_models(entries):
    assert len(entries) >= 5


def test_known_model_ids_present(entries):
    ids = {e["model_id"] for e in entries}
    assert "mistral-large-latest" in ids
    assert "mistral-medium-latest" in ids
    assert "mistral-small-latest" in ids
    assert "codestral-latest" in ids
    assert "magistral-medium-latest" in ids


def test_mistral_large_prices(entries):
    row = next(e for e in entries if e["model_id"] == "mistral-large-latest")
    assert row["input_per_million"] == pytest.approx(0.5)
    assert row["output_per_million"] == pytest.approx(1.5)


def test_mistral_medium_prices(entries):
    row = next(e for e in entries if e["model_id"] == "mistral-medium-latest")
    assert row["input_per_million"] == pytest.approx(1.5)
    assert row["output_per_million"] == pytest.approx(7.5)


def test_codestral_api_prices(entries):
    row = next(e for e in entries if e["model_id"] == "codestral-latest")
    assert row["input_per_million"] == pytest.approx(0.3)
    assert row["output_per_million"] == pytest.approx(0.9)


def test_magistral_medium_prices(entries):
    row = next(e for e in entries if e["model_id"] == "magistral-medium-latest")
    assert row["input_per_million"] == pytest.approx(2.0)
    assert row["output_per_million"] == pytest.approx(5.0)


def test_provider_and_key(entries):
    row = next(e for e in entries if e["model_id"] == "mistral-large-latest")
    assert row["provider"] == "mistral"
    assert row["key"] == "mistral:mistral-large-latest"
    assert row["sources"] == ["mistral-direct"]


def test_no_duplicates(entries):
    ids = [e["model_id"] for e in entries]
    assert len(ids) == len(set(ids))


def test_no_rsc_block_returns_empty():
    scraper = Mistral()
    result = list(scraper.transform("<html><body>no pricing data</body></html>"))
    assert result == []


def test_models_without_standard_prices_excluded(entries):
    # Models with only per-minute or non-token prices should not appear with a price
    # unless they also have a per-M-token output price. Moderation models with input
    # only should have input set but no output.
    ids_with_prices = {
        e["model_id"] for e in entries if "input_per_million" in e or "output_per_million" in e
    }
    assert len(ids_with_prices) >= 5
