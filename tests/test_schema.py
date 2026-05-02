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


def test_validate_document_invalid_provider() -> None:
    schema = load_schema(SCHEMA_PATH)
    doc = copy.deepcopy(MINIMAL_VALID)
    doc["models"][0]["provider"] = "not_a_provider"
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_document(doc, schema)
    assert exc_info.value.errors


def test_validate_document_invalid_capability() -> None:
    schema = load_schema(SCHEMA_PATH)
    doc = copy.deepcopy(MINIMAL_VALID)
    doc["models"][0]["capabilities"] = ["teleportation"]
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
