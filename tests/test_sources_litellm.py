import json
from pathlib import Path
from typing import Any

import pytest

from rate_card.sources.litellm import (
    LiteLLM,
    _build_capabilities,
    _build_pricing_tiers,
    _transform_entry,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "litellm-snapshot.json"


def load_fixture() -> dict[str, Any]:
    with open(FIXTURE_PATH) as fh:
        return json.load(fh)  # type: ignore[no-any-return]


def transformed_by_key(key: str) -> Any:
    source = LiteLLM(url="https://example.com", fixture_path=str(FIXTURE_PATH))
    raw = source.fetch()
    return {e["key"]: e for e in source.transform(raw)}.get(key)


# ── fetch ─────────────────────────────────────────────────────────────────────


def test_fetch_from_fixture() -> None:
    source = LiteLLM(url="https://example.com", fixture_path=str(FIXTURE_PATH))
    raw = source.fetch()
    assert "claude-sonnet-4-5" in raw
    assert "sample_spec" in raw


def test_use_fixture_method() -> None:
    source = LiteLLM(url="https://example.com")
    source.use_fixture(FIXTURE_PATH)
    raw = source.fetch()
    assert "gpt-4o" in raw


def test_source_attributes() -> None:
    source = LiteLLM(url="https://example.com")
    assert source.name == "litellm"
    assert source.role == "primary"
    assert source.enabled is True


# ── sample_spec skipped ───────────────────────────────────────────────────────


def test_sample_spec_is_skipped() -> None:
    source = LiteLLM(url="https://example.com", fixture_path=str(FIXTURE_PATH))
    raw = source.fetch()
    results = list(source.transform(raw))
    keys = [e["key"] for e in results]
    assert not any("sample_spec" in k for k in keys)


# ── provider mapping ──────────────────────────────────────────────────────────


def test_anthropic_provider_mapping() -> None:
    entry = transformed_by_key("anthropic:claude-sonnet-4-5")
    assert entry is not None
    assert entry["provider"] == "anthropic"


def test_openai_provider_mapping() -> None:
    entry = transformed_by_key("openai:gpt-4o")
    assert entry is not None
    assert entry["provider"] == "openai"


def test_gemini_provider_mapping() -> None:
    entry = transformed_by_key("gemini:gemini-2.0-flash")
    assert entry is not None
    assert entry["provider"] == "gemini"


def test_bedrock_provider_mapping() -> None:
    entry = transformed_by_key("bedrock:ap-northeast-1/anthropic.claude-instant-v1")
    assert entry is not None
    assert entry["provider"] == "bedrock"


# ── key derivation ────────────────────────────────────────────────────────────


def test_bedrock_prefix_stripped_from_model_id() -> None:
    entry = transformed_by_key("bedrock:ap-northeast-1/anthropic.claude-instant-v1")
    assert entry is not None
    assert entry["model_id"] == "ap-northeast-1/anthropic.claude-instant-v1"
    assert entry["key"] == "bedrock:ap-northeast-1/anthropic.claude-instant-v1"


def test_gemini_prefix_stripped_from_model_id() -> None:
    entry = transformed_by_key("gemini:gemini-2.0-flash")
    assert entry is not None
    assert entry["model_id"] == "gemini-2.0-flash"


def test_anthropic_key_format() -> None:
    entry = transformed_by_key("anthropic:claude-sonnet-4-5")
    assert entry is not None
    assert entry["key"] == "anthropic:claude-sonnet-4-5"
    assert entry["model_id"] == "claude-sonnet-4-5"


# ── unit conversion (per-token -> per-million) ────────────────────────────────


def test_input_per_million_conversion() -> None:
    entry = transformed_by_key("anthropic:claude-sonnet-4-5")
    assert entry is not None
    assert entry["input_per_million"] == pytest.approx(3.0)


def test_output_per_million_conversion() -> None:
    entry = transformed_by_key("anthropic:claude-sonnet-4-5")
    assert entry is not None
    assert entry["output_per_million"] == pytest.approx(15.0)


def test_gpt4o_pricing_conversion() -> None:
    entry = transformed_by_key("openai:gpt-4o")
    assert entry is not None
    assert entry["input_per_million"] == pytest.approx(2.5)
    assert entry["output_per_million"] == pytest.approx(10.0)


# ── cache pricing ─────────────────────────────────────────────────────────────


def test_cache_read_per_million() -> None:
    entry = transformed_by_key("anthropic:claude-sonnet-4-5")
    assert entry is not None
    assert entry["cache_read_per_million"] == pytest.approx(0.3)


def test_cache_write_per_million() -> None:
    entry = transformed_by_key("anthropic:claude-sonnet-4-5")
    assert entry is not None
    assert entry["cache_write_per_million"] == pytest.approx(3.75)


def test_haiku_cache_read() -> None:
    entry = transformed_by_key("anthropic:claude-3-haiku-20240307")
    assert entry is not None
    assert entry["cache_read_per_million"] == pytest.approx(0.03)
    assert entry["cache_write_per_million"] == pytest.approx(0.3)


def test_gpt4o_cache_read() -> None:
    entry = transformed_by_key("openai:gpt-4o")
    assert entry is not None
    assert entry["cache_read_per_million"] == pytest.approx(1.25)


def test_gemini_cache_read_only() -> None:
    entry = transformed_by_key("gemini:gemini-2.0-flash")
    assert entry is not None
    assert entry["cache_read_per_million"] == pytest.approx(0.025)
    assert "cache_write_per_million" not in entry


# ── tiered pricing ────────────────────────────────────────────────────────────


def test_tiered_pricing_threshold() -> None:
    entry = transformed_by_key("anthropic:claude-sonnet-4-5")
    assert entry is not None
    tiers = entry.get("pricing_tiers", [])
    assert len(tiers) == 1
    assert tiers[0]["above_input_tokens"] == 200_000


def test_tiered_pricing_values() -> None:
    entry = transformed_by_key("anthropic:claude-sonnet-4-5")
    assert entry is not None
    tier = entry["pricing_tiers"][0]
    assert tier["input_per_million"] == pytest.approx(6.0)
    assert tier["output_per_million"] == pytest.approx(22.5)
    assert tier["cache_read_per_million"] == pytest.approx(0.6)
    assert tier["cache_write_per_million"] == pytest.approx(7.5)


def test_no_tiers_when_not_present() -> None:
    entry = transformed_by_key("openai:gpt-4o")
    assert entry is not None
    assert "pricing_tiers" not in entry or entry.get("pricing_tiers") == []


# ── reasoning token pricing ───────────────────────────────────────────────────


def test_reasoning_per_million_mapped() -> None:
    # dashscope provider is not in our map, so use _transform_entry directly
    entry = _transform_entry(
        "my-reasoning-model",
        {
            "input_cost_per_token": 1e-06,
            "output_cost_per_token": 4e-06,
            "output_cost_per_reasoning_token": 4e-06,
            "litellm_provider": "openai",
            "max_input_tokens": 128000,
            "mode": "chat",
        },
    )
    assert entry is not None
    assert entry["reasoning_per_million"] == pytest.approx(4.0)


# ── capability mapping ────────────────────────────────────────────────────────


def test_tools_from_supports_function_calling() -> None:
    entry = transformed_by_key("openai:gpt-4o")
    assert entry is not None
    assert "tools" in entry["capabilities"]


def test_structured_output_from_supports_response_schema() -> None:
    entry = transformed_by_key("openai:gpt-4o")
    assert entry is not None
    assert "structured_output" in entry["capabilities"]


def test_prompt_caching_capability() -> None:
    entry = transformed_by_key("openai:gpt-4o")
    assert entry is not None
    assert "prompt_caching" in entry["capabilities"]


def test_vision_capability() -> None:
    entry = transformed_by_key("openai:gpt-4o")
    assert entry is not None
    assert "vision" in entry["capabilities"]


def test_audio_input_capability() -> None:
    entry = transformed_by_key("gemini:gemini-2.0-flash")
    assert entry is not None
    assert "audio_input" in entry["capabilities"]


def test_audio_output_capability() -> None:
    entry = transformed_by_key("gemini:gemini-2.0-flash")
    assert entry is not None
    assert "audio_output" in entry["capabilities"]


def test_web_search_capability() -> None:
    entry = transformed_by_key("gemini:gemini-2.0-flash")
    assert entry is not None
    assert "web_search" in entry["capabilities"]


def test_pdf_input_capability() -> None:
    entry = transformed_by_key("openai:gpt-4o")
    assert entry is not None
    assert "pdf_input" in entry["capabilities"]


def test_reasoning_capability() -> None:
    entry = transformed_by_key("openai:o1")
    assert entry is not None
    assert "reasoning" in entry["capabilities"]


def test_no_spurious_capabilities() -> None:
    entry = transformed_by_key("bedrock:ap-northeast-1/anthropic.claude-instant-v1")
    assert entry is not None
    # bedrock entry has only supports_tool_choice which is not in our capability map
    assert entry["capabilities"] == []


# ── deprecation date ──────────────────────────────────────────────────────────


def test_deprecation_date_passed_through() -> None:
    entry = transformed_by_key("gemini:gemini-2.0-flash")
    assert entry is not None
    assert entry.get("deprecation_date") == "2026-06-01"


def test_no_deprecation_date_when_absent() -> None:
    entry = transformed_by_key("anthropic:claude-sonnet-4-5")
    assert entry is not None
    assert "deprecation_date" not in entry


# ── source_url passthrough ────────────────────────────────────────────────────


def test_source_url_passed_through() -> None:
    entry = transformed_by_key("gemini:gemini-2.0-flash")
    assert entry is not None
    assert entry.get("source_url") == "https://ai.google.dev/pricing#2_0flash"


def test_no_source_url_when_absent() -> None:
    entry = transformed_by_key("openai:gpt-4o")
    assert entry is not None
    assert "source_url" not in entry


# ── context_window ────────────────────────────────────────────────────────────


def test_context_window_from_max_input_tokens() -> None:
    entry = transformed_by_key("anthropic:claude-sonnet-4-5")
    assert entry is not None
    assert entry["context_window"] == 200_000


def test_context_window_gemini() -> None:
    entry = transformed_by_key("gemini:gemini-2.0-flash")
    assert entry is not None
    assert entry["context_window"] == 1_048_576


# ── mode mapping ──────────────────────────────────────────────────────────────


def test_embedding_mode_preserved() -> None:
    entry = transformed_by_key("openai:text-embedding-3-large")
    assert entry is not None
    assert entry["mode"] == "embedding"


def test_chat_mode_default() -> None:
    entry = transformed_by_key("openai:gpt-4o")
    assert entry is not None
    assert entry["mode"] == "chat"


# ── missing field handling ────────────────────────────────────────────────────


def test_entry_without_input_cost_skipped() -> None:
    result = _transform_entry(
        "no-cost-model",
        {
            "litellm_provider": "openai",
            "mode": "chat",
            "max_input_tokens": 128000,
        },
    )
    assert result is None


def test_entry_without_output_cost_skipped() -> None:
    result = _transform_entry(
        "no-output-cost",
        {
            "litellm_provider": "openai",
            "input_cost_per_token": 1e-06,
            "mode": "chat",
            "max_input_tokens": 128000,
        },
    )
    assert result is None


def test_entry_with_unknown_provider_skipped() -> None:
    result = _transform_entry(
        "mystery-model",
        {
            "litellm_provider": "unknown_provider_xyz",
            "input_cost_per_token": 1e-06,
            "output_cost_per_token": 4e-06,
            "mode": "chat",
        },
    )
    assert result is None


def test_non_dict_entry_skipped() -> None:
    source = LiteLLM(url="https://example.com")
    raw = {"bad-entry": "just a string", "sample_spec": {}}
    results = list(source.transform(raw))
    assert results == []


# ── sources field ─────────────────────────────────────────────────────────────


def test_sources_contains_litellm() -> None:
    entry = transformed_by_key("openai:gpt-4o")
    assert entry is not None
    assert entry["sources"] == ["litellm"]


# ── build_capabilities edge cases ────────────────────────────────────────────


def test_build_capabilities_false_values_excluded() -> None:
    caps = _build_capabilities({"supports_vision": False, "supports_function_calling": True})
    assert "vision" not in caps
    assert "tools" in caps


def test_build_capabilities_unknown_supports_field_ignored() -> None:
    caps = _build_capabilities({"supports_unknown_field_xyz": True})
    assert caps == []


# ── build_pricing_tiers edge cases ───────────────────────────────────────────


def test_build_pricing_tiers_no_tier_when_absent() -> None:
    tiers = _build_pricing_tiers({})
    assert tiers == []


def test_build_pricing_tiers_partial_fields() -> None:
    tiers = _build_pricing_tiers({"input_cost_per_token_above_200k_tokens": 6e-06})
    assert len(tiers) == 1
    assert tiers[0]["above_input_tokens"] == 200_000
    assert tiers[0]["input_per_million"] == pytest.approx(6.0)
    assert "output_per_million" not in tiers[0]


@pytest.mark.parametrize(
    ("cost_per_token", "expected"),
    [
        (4e-07, 0.4),
        (1e-07, 0.1),
        (8e-07, 0.8),
        (1.25e-07, 0.125),
        (2.5e-08, 0.025),
        (3e-06, 3.0),
    ],
)
def test_per_million_conversion_rounds_fp_noise(cost_per_token: float, expected: float) -> None:
    entry = _transform_entry(
        "test-model",
        {
            "litellm_provider": "openai",
            "input_cost_per_token": cost_per_token,
            "output_cost_per_token": cost_per_token,
            "max_input_tokens": 1000,
            "mode": "chat",
        },
    )
    assert entry is not None
    assert entry["input_per_million"] == expected
    assert entry["output_per_million"] == expected
