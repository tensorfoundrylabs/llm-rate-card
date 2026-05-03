from pathlib import Path

import pytest

from rate_card.sources.qwen import Qwen

FIXTURE = Path(__file__).parent / "fixtures" / "scrapers" / "qwen.html"


@pytest.fixture()
def entries():
    scraper = Qwen()
    scraper.use_fixture(str(FIXTURE))
    raw = scraper.fetch()
    return list(scraper.transform(raw))


def test_extract_returns_many_models(entries):
    assert len(entries) >= 20


def test_known_model_ids_present(entries):
    ids = {e["model_id"] for e in entries}
    assert "qwen/qwen3-max" in ids
    assert "qwen/qwen-max" in ids
    assert "qwen/qwen-flash" in ids
    assert "qwen/qwen-turbo" in ids


def test_qwen3_max_base_prices(entries):
    row = next(e for e in entries if e["model_id"] == "qwen/qwen3-max")
    assert row["input_per_million"] == pytest.approx(1.2)
    assert row["output_per_million"] == pytest.approx(6.0)


def test_qwen3_max_has_pricing_tiers(entries):
    row = next(e for e in entries if e["model_id"] == "qwen/qwen3-max")
    tiers = row["pricing_tiers"]
    assert len(tiers) == 2
    t1 = tiers[0]
    assert t1["above_input_tokens"] == 32_000
    assert t1["input_per_million"] == pytest.approx(2.4)
    assert t1["output_per_million"] == pytest.approx(12.0)
    t2 = tiers[1]
    assert t2["above_input_tokens"] == 128_000
    assert t2["input_per_million"] == pytest.approx(3.0)
    assert t2["output_per_million"] == pytest.approx(15.0)


def test_qwen_max_flat_pricing(entries):
    row = next(e for e in entries if e["model_id"] == "qwen/qwen-max")
    assert row["input_per_million"] == pytest.approx(1.6)
    assert row["output_per_million"] == pytest.approx(6.4)
    assert "pricing_tiers" not in row


def test_qwen_flash_prices_and_tier(entries):
    row = next(e for e in entries if e["model_id"] == "qwen/qwen-flash")
    assert row["input_per_million"] == pytest.approx(0.05)
    assert row["output_per_million"] == pytest.approx(0.4)
    tiers = row.get("pricing_tiers", [])
    assert any(t["above_input_tokens"] == 256_000 for t in tiers)


def test_provider_and_key(entries):
    row = next(e for e in entries if e["model_id"] == "qwen/qwen-max")
    assert row["provider"] == "qwen"
    assert row["key"] == "qwen:qwen/qwen-max"
    assert row["sources"] == ["qwen-direct"]


def test_no_duplicates(entries):
    ids = [e["model_id"] for e in entries]
    assert len(ids) == len(set(ids))


def test_no_pricing_table_returns_empty():
    scraper = Qwen()
    result = list(scraper.transform("<html><body>no pricing</body></html>"))
    assert result == []
