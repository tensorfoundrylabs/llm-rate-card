import logging
from pathlib import Path
from typing import Any

import yaml

from rate_card.types import PartialEntry

logger = logging.getLogger(__name__)


def load_whitelist(path: str | Path) -> dict[str, list[str]]:
    """Load whitelist.yaml, returning a mapping of provider -> [model_id, ...]."""
    with open(path) as fh:
        raw: dict[str, Any] = yaml.safe_load(fh)
    return {provider: list(models) for provider, models in raw.items()}


def _whitelist_keys(whitelist: dict[str, list[str]]) -> frozenset[str]:
    return frozenset(
        f"{provider}:{model_id}" for provider, models in whitelist.items() for model_id in models
    )


def apply_whitelist(
    entries: list[PartialEntry],
    whitelist: dict[str, list[str]],
) -> tuple[list[PartialEntry], list[str]]:
    """Filter entries to those on the whitelist.

    Returns (kept, missing_from_source) where missing_from_source lists whitelist
    keys that had no corresponding entry in the source data.
    """
    allowed = _whitelist_keys(whitelist)
    seen: set[str] = set()
    kept: list[PartialEntry] = []

    for entry in entries:
        key = entry["key"]
        if key in allowed:
            kept.append(entry)
            seen.add(key)
        else:
            logger.debug("dropping %r (not in whitelist)", key)

    missing = sorted(allowed - seen)
    for key in missing:
        logger.warning("whitelist entry %r not found in source data", key)

    return kept, missing
