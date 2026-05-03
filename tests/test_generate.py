import json
import textwrap
from pathlib import Path
from typing import Any

from rate_card.generate import _build_document, _carry_forward_verified, run
from rate_card.schema import load_schema, validate_document
from rate_card.types import PartialEntry

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "litellm-snapshot.json"
SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "v1" / "schema.json"
CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
SOURCES_PATH = Path(__file__).parent.parent / "sources.yaml"


def _make_whitelist(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "whitelist.yaml"
    p.write_text(textwrap.dedent(content))
    return p


def _full_whitelist(tmp_path: Path) -> Path:
    return _make_whitelist(
        tmp_path,
        """
        anthropic:
          - claude-sonnet-4-5
          - claude-3-haiku-20240307
        openai:
          - gpt-4o
          - o1
          - text-embedding-3-large
        gemini:
          - gemini-2.0-flash
        bedrock:
          - ap-northeast-1/anthropic.claude-instant-v1
        """,
    )


def test_run_with_fixture(tmp_path: Path) -> None:
    wl = _full_whitelist(tmp_path)
    output = tmp_path / "rate-card.json"
    doc, divs = run(
        config_path=CONFIG_PATH,
        sources_path=SOURCES_PATH,
        whitelist_path=wl,
        output_path=output,
        use_fixture=True,
    )
    assert len(doc["models"]) == 7
    assert divs == []
    assert output.exists()


def test_run_output_validates_against_schema(tmp_path: Path) -> None:
    wl = _full_whitelist(tmp_path)
    output = tmp_path / "rate-card.json"
    doc, _ = run(
        config_path=CONFIG_PATH,
        sources_path=SOURCES_PATH,
        whitelist_path=wl,
        output_path=output,
        use_fixture=True,
    )
    schema = load_schema(SCHEMA_PATH)
    validate_document(doc, schema)  # type: ignore[arg-type]


def test_run_model_keys_present(tmp_path: Path) -> None:
    wl = _full_whitelist(tmp_path)
    output = tmp_path / "rate-card.json"
    doc, _ = run(
        config_path=CONFIG_PATH,
        sources_path=SOURCES_PATH,
        whitelist_path=wl,
        output_path=output,
        use_fixture=True,
    )
    keys = {m["key"] for m in doc["models"]}
    assert "anthropic:claude-sonnet-4-5" in keys
    assert "openai:gpt-4o" in keys
    assert "gemini:gemini-2.0-flash" in keys


def test_run_content_hash_present(tmp_path: Path) -> None:
    wl = _full_whitelist(tmp_path)
    output = tmp_path / "rate-card.json"
    doc, _ = run(
        config_path=CONFIG_PATH,
        sources_path=SOURCES_PATH,
        whitelist_path=wl,
        output_path=output,
        use_fixture=True,
    )
    assert doc["content_hash"].startswith("sha256:")


def test_run_writes_json_to_disk(tmp_path: Path) -> None:
    wl = _full_whitelist(tmp_path)
    output = tmp_path / "subdir" / "rate-card.json"
    run(
        config_path=CONFIG_PATH,
        sources_path=SOURCES_PATH,
        whitelist_path=wl,
        output_path=output,
        use_fixture=True,
    )
    assert output.exists()
    with open(output) as fh:
        on_disk = json.load(fh)
    assert on_disk["name"] == "TensorFoundry LLM Rate Card"


def test_run_with_previous_carries_verified(tmp_path: Path) -> None:
    wl = _full_whitelist(tmp_path)
    output = tmp_path / "rate-card.json"
    doc, _ = run(
        config_path=CONFIG_PATH,
        sources_path=SOURCES_PATH,
        whitelist_path=wl,
        output_path=output,
        use_fixture=True,
    )
    prev_verified = next(m["verified"] for m in doc["models"] if m["key"] == "openai:gpt-4o")

    previous_path = tmp_path / "previous.json"
    with open(previous_path, "w") as fh:
        json.dump(doc, fh)

    output2 = tmp_path / "rate-card-2.json"
    doc2, _ = run(
        config_path=CONFIG_PATH,
        sources_path=SOURCES_PATH,
        whitelist_path=wl,
        output_path=output2,
        previous_path=previous_path,
        use_fixture=True,
    )
    new_verified = next(m["verified"] for m in doc2["models"] if m["key"] == "openai:gpt-4o")
    assert new_verified == prev_verified


def test_run_version_override(tmp_path: Path) -> None:
    wl = _full_whitelist(tmp_path)
    output = tmp_path / "rate-card.json"
    doc, _ = run(
        config_path=CONFIG_PATH,
        sources_path=SOURCES_PATH,
        whitelist_path=wl,
        output_path=output,
        use_fixture=True,
        version="2026.05.02",
    )
    assert doc["release"]["version"] == "2026.05.02"


def test_run_whitelist_subset(tmp_path: Path) -> None:
    wl = _make_whitelist(tmp_path, "openai:\n  - gpt-4o\n")
    output = tmp_path / "rate-card.json"
    doc, _ = run(
        config_path=CONFIG_PATH,
        sources_path=SOURCES_PATH,
        whitelist_path=wl,
        output_path=output,
        use_fixture=True,
    )
    assert len(doc["models"]) == 1
    assert doc["models"][0]["key"] == "openai:gpt-4o"


def _partial_entry(key: str, input_price: float) -> PartialEntry:
    return {
        "key": key,
        "provider": "openai",  # type: ignore[typeddict-item]
        "model_id": key.split(":")[-1],
        "mode": "chat",
        "input_per_million": input_price,
        "output_per_million": input_price * 4,
        "context_window": 128000,
        "capabilities": [],
        "sources": ["litellm"],
    }


def test_carry_forward_verified_new_entry() -> None:
    entries = [_partial_entry("openai:gpt-4o", 2.5)]
    _carry_forward_verified(entries, {}, "2026-05-02")
    assert entries[0]["verified"] == "2026-05-02"


def test_carry_forward_verified_price_unchanged() -> None:
    entries = [_partial_entry("openai:gpt-4o", 2.5)]
    previous: dict[str, Any] = {
        "models": [
            {
                "key": "openai:gpt-4o",
                "input_per_million": 2.5,
                "output_per_million": 10.0,
                "cache_read_per_million": None,
                "cache_write_per_million": None,
                "reasoning_per_million": None,
                "verified": "2026-04-01",
            }
        ]
    }
    _carry_forward_verified(entries, previous, "2026-05-02")
    assert entries[0]["verified"] == "2026-04-01"


def test_carry_forward_verified_price_changed() -> None:
    entries = [_partial_entry("openai:gpt-4o", 3.0)]
    previous: dict[str, Any] = {
        "models": [
            {
                "key": "openai:gpt-4o",
                "input_per_million": 2.5,
                "output_per_million": 10.0,
                "verified": "2026-04-01",
            }
        ]
    }
    _carry_forward_verified(entries, previous, "2026-05-02")
    assert entries[0]["verified"] == "2026-05-02"


def test_build_document_carries_all_optional_schema_fields() -> None:
    """Every optional field in the schema model definition is preserved through _build_document.

    Derives the set of optional fields from the schema itself so any future schema
    additions trigger a test failure if _build_document is not updated to carry them.
    """
    schema = load_schema(SCHEMA_PATH)
    model_def = schema["$defs"]["model"]
    required: set[str] = set(model_def["required"])
    all_props: set[str] = set(model_def["properties"].keys())
    optional_fields = all_props - required

    entry: PartialEntry = {
        "key": "openai:test-model",
        "provider": "openai",  # type: ignore[typeddict-item]
        "model_id": "test-model",
        "mode": "chat",
        "input_per_million": 1.0,
        "output_per_million": 4.0,
        "cache_read_per_million": 0.1,
        "cache_write_per_million": 0.2,
        "reasoning_per_million": 0.5,
        "pricing_tiers": [{"above_input_tokens": 200000, "input_per_million": 2.0}],
        "context_window": 128000,
        "modality_pricing": {"audio": {"input_per_million": 10.0}},
        "max_output_tokens": 4096,
        "deprecation_date": "2026-12-31",
        "source_url": "https://example.com",
        "verified": "2026-05-02",
        "capabilities": [],
        "sources": ["litellm"],
    }

    doc = _build_document([entry], "2026.05.02", "2026-05-02T00:00:00Z", None)
    assert len(doc["models"]) == 1
    model = doc["models"][0]

    for field in optional_fields:
        assert field in model, f"optional field {field!r} was dropped by _build_document"
