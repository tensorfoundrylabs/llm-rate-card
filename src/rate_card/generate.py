import datetime
import json
import logging
from pathlib import Path
from typing import Any

from rate_card.config import Config, load_config
from rate_card.filter import apply_whitelist, load_whitelist
from rate_card.hashing import content_hash
from rate_card.merge import Divergence, merge
from rate_card.registries import cross_check_vocabulary, load_registries
from rate_card.schema import load_schema, validate_document
from rate_card.sources.base import Source, load_sources
from rate_card.types import Attribution, Document, FullEntry, PartialEntry, Release

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = "1.0.0"
_FIXTURE_PATH = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "litellm-snapshot.json"


def _carry_forward_verified(
    entries: list[PartialEntry],
    previous: dict[str, Any],
    today: str,
) -> None:
    prev_by_key: dict[str, dict[str, Any]] = {m["key"]: m for m in previous.get("models", [])}
    _price_fields = (
        "input_per_million",
        "output_per_million",
        "cache_read_per_million",
        "cache_write_per_million",
        "reasoning_per_million",
    )
    for entry in entries:
        key = entry["key"]
        prev = prev_by_key.get(key)
        if prev is None:
            entry["verified"] = today
            continue
        prices_match = all(entry.get(f) == prev.get(f) for f in _price_fields)
        entry["verified"] = prev.get("verified", today) if prices_match else today


def _build_document(
    entries: list[PartialEntry],
    version: str,
    generated_at: str,
    source_commit: str | None,
) -> Document:
    full_entries: list[FullEntry] = []
    for entry in entries:
        full: FullEntry = {
            "key": entry["key"],
            "provider": entry["provider"],
            "model_id": entry["model_id"],
            "mode": entry["mode"],
            "input_per_million": entry["input_per_million"],
            "output_per_million": entry["output_per_million"],
            "context_window": entry.get("context_window", 0),
            "capabilities": list(entry.get("capabilities", [])),
            "verified": entry.get("verified", generated_at[:10]),
            "sources": list(entry.get("sources", [])),
        }
        for optional in (
            "cache_read_per_million",
            "cache_write_per_million",
            "reasoning_per_million",
            "pricing_tiers",
            "modality_pricing",
            "max_output_tokens",
            "deprecation_date",
            "source_url",
        ):
            if optional in entry:
                full[optional] = entry[optional]
        full_entries.append(full)

    release: Release = {
        "version": version,
        "generated_at": generated_at,
    }
    if source_commit:
        release["source_commit"] = source_commit

    attribution: list[Attribution] = [
        {
            "name": "LiteLLM",
            "license": "MIT",
            "url": "https://github.com/BerriAI/litellm",
            "role": "primary data source",
        }
    ]

    doc: Document = {
        "schema_version": _SCHEMA_VERSION,
        "name": "TensorFoundry LLM Rate Card",
        "author": "TensorFoundry Pty Ltd",
        "homepage": "https://github.com/tensorfoundrylabs/llm-rate-card",
        "license": "MIT",
        "license_url": "https://github.com/tensorfoundrylabs/llm-rate-card/blob/main/LICENSE",
        "attribution": attribution,
        "currency": "USD",
        "release": release,
        "content_hash": content_hash(full_entries),
        "models": full_entries,
    }
    return doc


def run(
    config_path: str | Path = "config.yaml",
    sources_path: str | Path = "sources.yaml",
    whitelist_path: str | Path = "whitelist.yaml",
    schema_path: str | Path | None = None,
    previous_path: str | Path | None = None,
    output_path: str | Path = "rate-card.json",
    use_fixture: bool = False,
    version: str | None = None,
    source_commit: str | None = None,
) -> tuple[Document, list[Divergence]]:
    """Run the full generation pipeline and write output_path."""
    cfg: Config = load_config(config_path)
    resolved_schema = schema_path or cfg.schema_path
    schema = load_schema(resolved_schema)
    whitelist = load_whitelist(whitelist_path)

    sources: list[Source] = load_sources(sources_path)

    if use_fixture:
        for source in sources:
            if hasattr(source, "use_fixture"):
                source.use_fixture(_FIXTURE_PATH)

    entries_by_source: dict[str, list[PartialEntry]] = {}
    for source in sources:
        if not source.enabled:
            continue
        logger.info("fetching from source %r", source.name)
        raw = source.fetch()
        entries_by_source[source.name] = list(source.transform(raw))
        logger.info(
            "source %r produced %d entries", source.name, len(entries_by_source[source.name])
        )

    merged_entries, divergences = merge(entries_by_source, cfg.divergence_threshold)
    kept, missing = apply_whitelist(merged_entries, whitelist)

    if missing:
        logger.warning(
            "%d whitelist entries not found in source data: %s", len(missing), missing[:10]
        )

    today = datetime.date.today().isoformat()

    previous: dict[str, Any] = {}
    if previous_path:
        with open(previous_path) as fh:
            previous = json.load(fh)

    _carry_forward_verified(kept, previous, today)

    release_version = version or today.replace("-", ".")
    generated_at = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")

    doc = _build_document(kept, release_version, generated_at, source_commit)

    validate_document(doc, schema)  # type: ignore[arg-type]

    registries = load_registries(cfg.registries_path)
    cross_check_vocabulary(doc, registries)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as fh:
        json.dump(doc, fh, indent=2)

    logger.info("wrote %d models to %s", len(kept), output)

    if divergences:
        divergence_path = output.with_suffix(".divergences.json")
        with open(divergence_path, "w") as fh:
            json.dump(
                [
                    {
                        "key": d.key,
                        "field": d.field,
                        "primary_value": d.primary_value,
                        "secondary_source": d.secondary_source,
                        "secondary_value": d.secondary_value,
                        "delta_pct": d.delta_pct,
                    }
                    for d in divergences
                ],
                fh,
                indent=2,
            )

    return doc, divergences
