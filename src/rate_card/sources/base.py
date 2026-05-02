import importlib
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal

import yaml

from rate_card.types import PartialEntry


class Source:
    """Protocol that every source must implement."""

    name: str
    role: Literal["primary", "secondary"]
    enabled: bool

    def fetch(self) -> Any:
        raise NotImplementedError

    def transform(self, raw: Any) -> Iterable[PartialEntry]:
        raise NotImplementedError


def load_sources(path: str | Path) -> list[Source]:
    """Load and instantiate sources from sources.yaml."""
    with open(path) as fh:
        raw: list[dict[str, Any]] = yaml.safe_load(fh)

    sources: list[Source] = []
    for entry in raw:
        if not entry.get("enabled", True):
            continue
        module_path: str = entry["module"]
        class_name: str = entry["class"]
        kwargs: dict[str, Any] = {k: v for k, v in entry.items() if k not in ("module", "class")}
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        sources.append(cls(**kwargs))

    return sources
