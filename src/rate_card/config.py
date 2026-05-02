from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Config:
    litellm_url: str
    schema_path: str
    divergence_threshold: float


_REQUIRED = {"litellm_url", "schema_path", "divergence_threshold"}


def load_config(path: str | Path = "config.yaml") -> Config:
    """Load config.yaml and return a Config instance."""
    with open(path) as fh:
        raw: dict[str, Any] = yaml.safe_load(fh)

    missing = _REQUIRED - raw.keys()
    if missing:
        raise ValueError(f"config.yaml missing required keys: {sorted(missing)}")

    threshold = float(raw["divergence_threshold"])
    if not (0.0 < threshold < 1.0):
        raise ValueError(f"divergence_threshold must be between 0 and 1, got {threshold}")

    return Config(
        litellm_url=str(raw["litellm_url"]),
        schema_path=str(raw["schema_path"]),
        divergence_threshold=threshold,
    )
