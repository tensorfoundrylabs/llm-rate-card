import hashlib
import json
from typing import Any


def content_hash(models: list[Any]) -> str:
    """Return sha256 over the canonicalised models array.

    Keys sorted and separators fixed so the hash is deterministic regardless
    of insertion order or formatting.
    """
    canonical = json.dumps(models, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return f"sha256:{digest}"
