import json
from pathlib import Path
from typing import TypedDict

from rate_card.types import Document


class Registries(TypedDict):
    providers: list[str]
    modes: list[str]
    capabilities: list[str]


def load_registries(path: str | Path) -> Registries:
    """Load and return the registries vocabulary file."""
    with open(path) as fh:
        return json.load(fh)  # type: ignore[no-any-return]


def cross_check_vocabulary(doc: Document, registries: Registries) -> None:
    """Raise ValueError if any provider, mode, or capability in doc is not in the registries."""
    known_providers = set(registries["providers"])
    known_modes = set(registries["modes"])
    known_capabilities = set(registries["capabilities"])

    for model in doc["models"]:
        key = model["key"]
        provider = model["provider"]
        if provider not in known_providers:
            raise ValueError(
                f"unknown provider {provider!r} in model {key!r} -- add it to registries.json"
            )
        mode = model["mode"]
        if mode not in known_modes:
            raise ValueError(f"unknown mode {mode!r} in model {key!r} -- add it to registries.json")
        for cap in model.get("capabilities", []):
            if cap not in known_capabilities:
                raise ValueError(
                    f"unknown capability {cap!r} in model {key!r} -- add it to registries.json"
                )
