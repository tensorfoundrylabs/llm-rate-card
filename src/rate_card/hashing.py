import hashlib
import json
from typing import Any

# Audit and provenance fields that change on every run without reflecting price or
# capability changes. Excluding them keeps the hash stable when content is unchanged.
_EXCLUDED_KEYS = frozenset({"verified", "sources"})


def content_hash(models: list[Any]) -> str:
    """Return sha256 over the canonicalised models array, excluding audit metadata."""
    stripped = [{k: v for k, v in m.items() if k not in _EXCLUDED_KEYS} for m in models]
    canonical = json.dumps(stripped, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return f"sha256:{digest}"
