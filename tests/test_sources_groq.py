from pathlib import Path

import pytest

from rate_card.sources.groq import Groq

FIXTURE = Path(__file__).parent / "fixtures" / "scrapers" / "groq.html"


@pytest.fixture()
def entries():
    scraper = Groq()
    scraper.use_fixture(str(FIXTURE))
    raw = scraper.fetch()
    return list(scraper.transform(raw))


def test_extract_returns_models(entries):
    assert len(entries) >= 4


def test_llama33_70b_prices(entries):
    row = next(e for e in entries if e["model_id"] == "groq/llama-3.3-70b-versatile")
    assert row["input_per_million"] == pytest.approx(0.59)
    assert row["output_per_million"] == pytest.approx(0.79)


def test_namespaced_model_id_present(entries):
    ids = {e["model_id"] for e in entries}
    assert "groq/openai/gpt-oss-120b" in ids
    assert "groq/openai/gpt-oss-20b" in ids


def test_kimi_prices(entries):
    row = next(e for e in entries if e["model_id"] == "groq/moonshotai/kimi-k2-instruct-0905")
    assert row["input_per_million"] == pytest.approx(1.0)
    assert row["output_per_million"] == pytest.approx(3.0)


def test_cache_read_on_namespaced_models(entries):
    row = next(e for e in entries if e["model_id"] == "groq/openai/gpt-oss-120b")
    assert "cache_read_per_million" in row
    # Cached input column ($0.075) is distinct from uncached input ($0.15)
    assert row["cache_read_per_million"] == pytest.approx(0.075)
    assert row["input_per_million"] == pytest.approx(0.15)


def test_provider_and_key(entries):
    row = next(e for e in entries if e["model_id"] == "groq/llama-3.3-70b-versatile")
    assert row["provider"] == "groq"
    assert row["key"] == "groq:groq/llama-3.3-70b-versatile"
    assert row["sources"] == ["groq-direct"]


def test_audio_table_excluded(entries):
    # Audio transcription models should not appear (no input/output token columns)
    ids = {e["model_id"] for e in entries}
    assert all("whisper" not in mid.lower() for mid in ids)


def test_no_duplicates(entries):
    ids = [e["model_id"] for e in entries]
    assert len(ids) == len(set(ids))


def test_malformed_price_row_excluded():
    html = """
    <table>
      <thead><tr><th>AI Model</th><th>Input Token Price</th><th>Output Token Price</th></tr></thead>
      <tbody>
        <tr><td>Test Model</td><td>not-a-price</td><td>also-not</td></tr>
      </tbody>
    </table>
    """
    scraper = Groq()
    result = list(scraper.transform(html))
    assert all("test-model" not in e["model_id"] for e in result)
