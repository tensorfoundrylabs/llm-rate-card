import copy
from pathlib import Path
from typing import Any

import pytest

from rate_card.schema import SchemaValidationError, load_schema, validate_document

SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "v1" / "schema.json"

MINIMAL_VALID: dict[str, Any] = {
    "$schema": "https://schema.tensorfoundry.io/rate-card/v1/schema.json",
    "schema_version": "1.0.0",
    "name": "TensorFoundry LLM Rate Card",
    "author": "TensorFoundry Pty Ltd",
    "homepage": "https://github.com/tensorfoundrylabs/llm-rate-card",
    "license": "MIT",
    "currency": "USD",
    "release": {
        "version": "2026.05.02",
        "generated_at": "2026-05-02T03:00:00Z",
    },
    "content_hash": "sha256:" + "a" * 64,
    "models": [
        {
            "key": "openai:gpt-4o",
            "provider": "openai",
            "model_id": "gpt-4o",
            "mode": "chat",
            "input_per_million": 2.5,
            "output_per_million": 10.0,
            "context_window": 128000,
            "capabilities": ["streaming", "vision"],
            "verified": "2026-05-02",
            "sources": ["litellm"],
        }
    ],
}


def test_load_schema() -> None:
    schema = load_schema(SCHEMA_PATH)
    assert schema["$id"] == "https://schema.tensorfoundry.io/rate-card/v1/schema.json"


def test_validate_document_valid() -> None:
    schema = load_schema(SCHEMA_PATH)
    validate_document(MINIMAL_VALID, schema)


def test_validate_document_missing_required_field() -> None:
    schema = load_schema(SCHEMA_PATH)
    doc = copy.deepcopy(MINIMAL_VALID)
    del doc["content_hash"]
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_document(doc, schema)
    assert "content_hash" in str(exc_info.value.errors)


def test_validate_document_invalid_provider_pattern() -> None:
    # provider must match ^[a-z][a-z0-9_]*$ -- uppercase is rejected
    schema = load_schema(SCHEMA_PATH)
    doc = copy.deepcopy(MINIMAL_VALID)
    doc["models"][0]["provider"] = "OpenAI"
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_document(doc, schema)
    assert exc_info.value.errors


def test_validate_document_unknown_provider_passes_schema() -> None:
    # the schema accepts any snake_case identifier; registries cross-check is the strict gate
    schema = load_schema(SCHEMA_PATH)
    doc = copy.deepcopy(MINIMAL_VALID)
    doc["models"][0]["provider"] = "new_provider_xyz"
    validate_document(doc, schema)  # must not raise


def test_validate_document_invalid_capability_pattern() -> None:
    # capability must match ^[a-z][a-z0-9_]*$ -- leading digit is rejected
    schema = load_schema(SCHEMA_PATH)
    doc = copy.deepcopy(MINIMAL_VALID)
    doc["models"][0]["capabilities"] = ["1invalid"]
    with pytest.raises(SchemaValidationError):
        validate_document(doc, schema)


def test_validate_document_invalid_content_hash_pattern() -> None:
    schema = load_schema(SCHEMA_PATH)
    doc = copy.deepcopy(MINIMAL_VALID)
    doc["content_hash"] = "md5:abc123"
    with pytest.raises(SchemaValidationError):
        validate_document(doc, schema)


def test_validate_document_pricing_tiers() -> None:
    schema = load_schema(SCHEMA_PATH)
    doc = copy.deepcopy(MINIMAL_VALID)
    doc["models"][0]["pricing_tiers"] = [
        {
            "above_input_tokens": 200000,
            "input_per_million": 6.0,
            "output_per_million": 22.5,
        }
    ]
    validate_document(doc, schema)


def test_schema_validation_error_has_errors_list() -> None:
    schema = load_schema(SCHEMA_PATH)
    doc = copy.deepcopy(MINIMAL_VALID)
    del doc["currency"]
    del doc["license"]
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_document(doc, schema)
    assert len(exc_info.value.errors) >= 2


def test_validate_modality_pricing_valid() -> None:
    schema = load_schema(SCHEMA_PATH)
    doc = copy.deepcopy(MINIMAL_VALID)
    doc["models"][0]["modality_pricing"] = {
        "audio": {
            "input_per_million": 32.0,
            "output_per_million": 64.0,
            "cache_read_per_million": 0.4,
        },
        "image": {
            "input_per_million": 5.0,
            "output_per_million": None,
        },
    }
    validate_document(doc, schema)  # must not raise


def test_validate_modality_pricing_missing_input_fails() -> None:
    schema = load_schema(SCHEMA_PATH)
    doc = copy.deepcopy(MINIMAL_VALID)
    doc["models"][0]["modality_pricing"] = {
        "audio": {"output_per_million": 64.0},
    }
    with pytest.raises(SchemaValidationError):
        validate_document(doc, schema)


def test_validate_modality_pricing_negative_value_fails() -> None:
    schema = load_schema(SCHEMA_PATH)
    doc = copy.deepcopy(MINIMAL_VALID)
    doc["models"][0]["modality_pricing"] = {
        "audio": {"input_per_million": -1.0},
    }
    with pytest.raises(SchemaValidationError):
        validate_document(doc, schema)


def test_validate_modality_pricing_extra_property_fails() -> None:
    schema = load_schema(SCHEMA_PATH)
    doc = copy.deepcopy(MINIMAL_VALID)
    doc["models"][0]["modality_pricing"] = {
        "audio": {"input_per_million": 32.0, "unexpected_field": "bad"},
    }
    with pytest.raises(SchemaValidationError):
        validate_document(doc, schema)


def test_validate_image_gen_without_context_window_and_output() -> None:
    schema = load_schema(SCHEMA_PATH)
    doc = copy.deepcopy(MINIMAL_VALID)
    doc["models"].append(
        {
            "key": "openai:gpt-image-2",
            "provider": "openai",
            "model_id": "gpt-image-2",
            "mode": "image_generation",
            "input_per_million": 5.0,
            "capabilities": ["vision"],
            "verified": "2026-05-02",
            "sources": ["litellm"],
        }
    )
    validate_document(doc, schema)  # must not raise


def test_validate_image_gen_context_window_still_enforced_when_present() -> None:
    schema = load_schema(SCHEMA_PATH)
    doc = copy.deepcopy(MINIMAL_VALID)
    doc["models"].append(
        {
            "key": "openai:gpt-image-2",
            "provider": "openai",
            "model_id": "gpt-image-2",
            "mode": "image_generation",
            "input_per_million": 5.0,
            "context_window": 0,
            "capabilities": [],
            "verified": "2026-05-02",
            "sources": ["litellm"],
        }
    )
    with pytest.raises(SchemaValidationError):
        validate_document(doc, schema)


def test_validate_image_gen_output_still_enforced_when_present() -> None:
    schema = load_schema(SCHEMA_PATH)
    doc = copy.deepcopy(MINIMAL_VALID)
    doc["models"].append(
        {
            "key": "openai:gpt-image-2",
            "provider": "openai",
            "model_id": "gpt-image-2",
            "mode": "image_generation",
            "input_per_million": 5.0,
            "output_per_million": -1.0,
            "capabilities": [],
            "verified": "2026-05-02",
            "sources": ["litellm"],
        }
    )
    with pytest.raises(SchemaValidationError):
        validate_document(doc, schema)
