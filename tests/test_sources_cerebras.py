from pathlib import Path

import pytest

from rate_card.sources.cerebras import Cerebras

FIXTURE = Path(__file__).parent / "fixtures" / "scrapers" / "cerebras.html"


@pytest.fixture()
def entries():
    scraper = Cerebras()
    scraper.use_fixture(str(FIXTURE))
    raw = scraper.fetch()
    return list(scraper.transform(raw))


def test_extract_returns_at_least_three_models(entries):
    assert len(entries) >= 3


def test_known_model_ids_present(entries):
    ids = {e["model_id"] for e in entries}
    assert "cerebras/llama3.1-8b" in ids
    assert "cerebras/gpt-oss-120b" in ids
    assert "cerebras/zai-glm-4.7" in ids


def test_glm47_prices(entries):
    row = next(e for e in entries if e["model_id"] == "cerebras/zai-glm-4.7")
    assert row["input_per_million"] == pytest.approx(2.25)
    assert row["output_per_million"] == pytest.approx(2.75)


def test_gpt_oss_prices(entries):
    row = next(e for e in entries if e["model_id"] == "cerebras/gpt-oss-120b")
    assert row["input_per_million"] == pytest.approx(0.35)
    assert row["output_per_million"] == pytest.approx(0.75)


def test_llama_prices(entries):
    row = next(e for e in entries if e["model_id"] == "cerebras/llama3.1-8b")
    assert row["input_per_million"] == pytest.approx(0.10)
    assert row["output_per_million"] == pytest.approx(0.10)


def test_provider_and_key(entries):
    row = next(e for e in entries if e["model_id"] == "cerebras/llama3.1-8b")
    assert row["provider"] == "cerebras"
    assert row["key"] == "cerebras:cerebras/llama3.1-8b"
    assert row["sources"] == ["cerebras-direct"]


def test_no_duplicates(entries):
    ids = [e["model_id"] for e in entries]
    assert len(ids) == len(set(ids))


def test_missing_rsc_block_returns_empty():
    scraper = Cerebras()
    result = list(scraper.transform("<html><body>no pricing</body></html>"))
    assert result == []
