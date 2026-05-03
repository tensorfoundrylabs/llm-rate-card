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


# ── multi-modal extraction ────────────────────────────────────────────────────


def test_realtime_model_has_text_top_level_rates(entries):
    row = next(e for e in entries if e["model_id"] == "gpt-realtime-1.5")
    assert row["input_per_million"] == pytest.approx(4.0)
    assert row["output_per_million"] == pytest.approx(16.0)
    assert row["cache_read_per_million"] == pytest.approx(0.4)


def test_realtime_model_has_audio_modality_pricing(entries):
    row = next(e for e in entries if e["model_id"] == "gpt-realtime-1.5")
    assert "modality_pricing" in row
    mp = row["modality_pricing"]
    assert "audio" in mp
    assert mp["audio"]["input_per_million"] == pytest.approx(32.0)
    assert mp["audio"]["output_per_million"] == pytest.approx(64.0)
    assert mp["audio"]["cache_read_per_million"] == pytest.approx(0.4)


def test_realtime_model_has_image_modality_pricing(entries):
    row = next(e for e in entries if e["model_id"] == "gpt-realtime-1.5")
    mp = row["modality_pricing"]
    assert "image" in mp
    assert mp["image"]["input_per_million"] == pytest.approx(5.0)
    assert mp["image"].get("output_per_million") is None
    assert mp["image"]["cache_read_per_million"] == pytest.approx(0.5)


def test_realtime_model_text_not_in_modality_pricing(entries):
    row = next(e for e in entries if e["model_id"] == "gpt-realtime-1.5")
    mp = row.get("modality_pricing", {})
    assert "text" not in mp


def test_image_model_has_modality_pricing(entries):
    row = next(e for e in entries if e["model_id"] == "gpt-image-2")
    assert "modality_pricing" in row
    mp = row["modality_pricing"]
    assert "image" in mp
    assert mp["image"]["input_per_million"] == pytest.approx(8.0)
    assert mp["image"]["output_per_million"] == pytest.approx(30.0)
    assert mp["image"]["cache_read_per_million"] == pytest.approx(2.0)


def test_image_model_has_text_top_level(entries):
    row = next(e for e in entries if e["model_id"] == "gpt-image-2")
    assert row["input_per_million"] == pytest.approx(5.0)
    assert row["cache_read_per_million"] == pytest.approx(1.25)


def test_single_modality_model_no_modality_pricing(entries):
    # gpt-5.5 has only one modality (text) with short/long context split; no modality_pricing key
    row = next(e for e in entries if e["model_id"] == "gpt-5.5")
    assert "modality_pricing" not in row


# ── batch rates not picked up ────────────────────────────────────────────────


def test_standard_rates_not_batch_for_gpt55(entries):
    # Standard gpt-5.5 input = $5.00; Batch = $2.50 (half). We must get Standard.
    row = next(e for e in entries if e["model_id"] == "gpt-5.5")
    assert row["input_per_million"] == pytest.approx(5.0)
    assert row["input_per_million"] != pytest.approx(2.5)


def test_standard_rates_not_batch_for_gpt54(entries):
    # Standard gpt-5.4 input = $2.50; Batch = $1.25. We must get Standard.
    row = next(e for e in entries if e["model_id"] == "gpt-5.4")
    assert row["input_per_million"] == pytest.approx(2.5)
    assert row["input_per_million"] != pytest.approx(1.25)


def test_batch_table_not_present_in_results():
    # Construct a page with both Standard and Batch tables for the same model
    html = """
    <div data-value="standard">
      <table>
        <thead><tr><th>Model</th><th>Input</th><th>Output</th></tr></thead>
        <tbody><tr><td>my-model</td><td>$10.00</td><td>$30.00</td></tr></tbody>
      </table>
    </div>
    <div data-value="batch">
      <table>
        <thead><tr><th>Model</th><th>Input</th><th>Output</th></tr></thead>
        <tbody><tr><td>my-model</td><td>$5.00</td><td>$15.00</td></tr></tbody>
      </table>
    </div>
    """
    scraper = OpenAI()
    result = list(scraper.transform(html))
    assert len(result) == 1
    assert result[0]["input_per_million"] == pytest.approx(10.0)


# ── cache_read flows through for both top-level and modality ─────────────────


def test_cache_read_in_modality_pricing(entries):
    row = next(e for e in entries if e["model_id"] == "gpt-realtime-1.5")
    mp = row["modality_pricing"]
    assert mp["audio"].get("cache_read_per_million") == pytest.approx(0.4)


def test_cache_read_in_text_top_level_for_multimodal(entries):
    row = next(e for e in entries if e["model_id"] == "gpt-image-2")
    assert row.get("cache_read_per_million") == pytest.approx(1.25)


def test_cache_read_column_standard_table(entries):
    # gpt-5.5 standard table has Cached input column
    row = next(e for e in entries if e["model_id"] == "gpt-5.5")
    assert row.get("cache_read_per_million") == pytest.approx(0.5)
