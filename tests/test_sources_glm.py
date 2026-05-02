from pathlib import Path

import pytest

from rate_card.sources.glm import GLM

FIXTURE = Path(__file__).parent / "fixtures" / "scrapers" / "glm.html"


@pytest.fixture()
def entries():
    scraper = GLM()
    scraper.use_fixture(str(FIXTURE))
    raw = scraper.fetch()
    return list(scraper.transform(raw))


def test_extract_returns_models(entries):
    assert len(entries) >= 4


def test_model_ids_present(entries):
    ids = {e["model_id"] for e in entries}
    assert "GLM-5.1" in ids
    assert "GLM-5" in ids
    assert "GLM-4.7" in ids


def test_glm51_prices(entries):
    row = next(e for e in entries if e["model_id"] == "GLM-5.1")
    assert row["input_per_million"] == pytest.approx(1.4)
    assert row["output_per_million"] == pytest.approx(4.4)


def test_glm5_prices(entries):
    row = next(e for e in entries if e["model_id"] == "GLM-5")
    assert row["input_per_million"] == pytest.approx(1.0)
    assert row["output_per_million"] == pytest.approx(3.2)


def test_glm47_prices(entries):
    row = next(e for e in entries if e["model_id"] == "GLM-4.7")
    assert row["input_per_million"] == pytest.approx(0.6)
    assert row["output_per_million"] == pytest.approx(2.2)


def test_free_model_excluded(entries):
    # Free models have no price data and should be excluded
    ids = {e["model_id"] for e in entries}
    assert "GLM-4.7-Flash" not in ids


def test_cache_read_present_on_paid_model(entries):
    row = next(e for e in entries if e["model_id"] == "GLM-5.1")
    assert "cache_read_per_million" in row
    assert row["cache_read_per_million"] == pytest.approx(0.26)


def test_provider_and_key(entries):
    row = next(e for e in entries if e["model_id"] == "GLM-5.1")
    assert row["provider"] == "glm"
    assert row["key"] == "glm:GLM-5.1"
    assert row["sources"] == ["glm-direct"]


def test_malformed_price_row_excluded():
    html = """
    <table>
      <thead><tr><th>Model</th><th>Input</th><th>Output</th></tr></thead>
      <tbody>
        <tr><td>GLM-X</td><td>not-a-price</td><td>also-not</td></tr>
      </tbody>
    </table>
    """
    scraper = GLM()
    result = list(scraper.transform(html))
    assert all(e["model_id"] != "GLM-X" for e in result)
