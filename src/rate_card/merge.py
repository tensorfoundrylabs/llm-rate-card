import logging
from dataclasses import dataclass
from typing import Any

from rate_card.types import PartialEntry

logger = logging.getLogger(__name__)

_PRICE_FIELDS = (
    "input_per_million",
    "output_per_million",
    "cache_read_per_million",
    "cache_write_per_million",
    "reasoning_per_million",
)


@dataclass
class Divergence:
    key: str
    field: str
    primary_value: float
    secondary_source: str
    secondary_value: float
    delta_pct: float


def _check_divergence(
    key: str,
    field: str,
    primary_value: float,
    secondary_source: str,
    secondary_value: float,
    threshold: float,
) -> Divergence | None:
    if primary_value == 0:
        return None
    delta = abs(secondary_value - primary_value) / primary_value
    if delta > threshold:
        return Divergence(
            key=key,
            field=field,
            primary_value=primary_value,
            secondary_source=secondary_source,
            secondary_value=secondary_value,
            delta_pct=delta,
        )
    return None


def _overlay(base: dict[str, Any], overlay: dict[str, Any]) -> None:
    for field, value in overlay.items():
        if field in ("key", "sources"):
            continue
        if (
            field == "modality_pricing"
            and isinstance(value, dict)
            and isinstance(base.get(field), dict)
        ):
            # Deep-merge: secondary adds or replaces individual modality keys without
            # discarding modalities already present in base.
            merged_mp: dict[str, Any] = dict(base[field])
            merged_mp.update(value)
            base[field] = merged_mp
        elif value is not None:
            base[field] = value


def _to_dict(entry: PartialEntry) -> dict[str, Any]:
    return dict(entry.items())


def merge(
    entries_by_source: dict[str, list[PartialEntry]],
    threshold: float,
) -> tuple[list[PartialEntry], list[Divergence]]:
    """Merge entries from multiple sources into a single list with divergence tracking.

    entries_by_source must have exactly one primary source. Secondaries are applied
    in iteration order; last non-null value wins per field.
    """
    primary_source_name: str | None = None
    merged: dict[str, dict[str, Any]] = {}
    secondary_sources: list[tuple[str, list[PartialEntry]]] = []

    for source_name, entries in entries_by_source.items():
        if primary_source_name is None:
            primary_source_name = source_name
            for entry in entries:
                merged[entry["key"]] = _to_dict(entry)
        else:
            secondary_sources.append((source_name, entries))

    divergences: list[Divergence] = []

    for source_name, entries in secondary_sources:
        for entry in entries:
            key = entry["key"]
            entry_dict = _to_dict(entry)
            if key not in merged:
                entry_dict["sources"] = [source_name]
                merged[key] = entry_dict
                continue

            base = merged[key]
            for field in _PRICE_FIELDS:
                secondary_value = entry_dict.get(field)
                primary_value = base.get(field)
                if secondary_value is not None and primary_value is not None:
                    div = _check_divergence(
                        key,
                        field,
                        float(primary_value),
                        source_name,
                        float(secondary_value),
                        threshold,
                    )
                    if div:
                        divergences.append(div)
                        logger.warning(
                            "price divergence on %r field %r: primary=%.4f secondary(%s)=%.4f (%.1f%%)",
                            key,
                            field,
                            primary_value,
                            source_name,
                            secondary_value,
                            div.delta_pct * 100,
                        )

            _overlay(base, entry_dict)

            existing_sources: list[str] = list(base.get("sources", []))
            if source_name not in existing_sources:
                existing_sources.append(source_name)
            base["sources"] = existing_sources

    result: list[PartialEntry] = list(merged.values())  # type: ignore[arg-type]
    return result, divergences
