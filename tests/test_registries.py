import json
from pathlib import Path
from typing import Any

import pytest

from rate_card.registries import Registries, cross_check_vocabulary, load_registries
from rate_card.types import Document, FullEntry

REGISTRIES_PATH = Path(__file__).parent.parent / "schema" / "v1" / "registries.json"


def _write_registries(tmp_path: Path, data: dict[str, Any]) -> Path:
    p = tmp_path / "registries.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _make_doc(models: list[FullEntry]) -> Document:
    return {
        "schema_version": "1.0.0",
        "name": "TensorFoundry LLM Rate Card",
        "author": "TensorFoundry Pty Ltd",
        "homepage": "https://github.com/tensorfoundrylabs/llm-rate-card",
        "license": "MIT",
        "currency": "USD",
        "release": {"version": "2026.05.02", "generated_at": "2026-05-02T00:00:00Z"},
        "content_hash": "sha256:" + "a" * 64,
        "models": models,
    }


def _make_model(
    key: str = "openai:gpt-4o",
    provider: str = "openai",
    mode: str = "chat",
    capabilities: list[str] | None = None,
) -> FullEntry:
    return {
        "key": key,
        "provider": provider,  # type: ignore[typeddict-item]
        "model_id": key.split(":")[-1],
        "mode": mode,  # type: ignore[typeddict-item]
        "input_per_million": 2.5,
        "output_per_million": 10.0,
        "context_window": 128000,
        "capabilities": capabilities or [],  # type: ignore[typeddict-item]
        "verified": "2026-05-02",
        "sources": ["stub"],
    }


# ── load_registries ────────────────────────────────────────────────────────────


def test_load_registries_parses_real_file() -> None:
    reg = load_registries(REGISTRIES_PATH)
    assert "openai" in reg["providers"]
    assert "anthropic" in reg["providers"]
    assert "chat" in reg["modes"]
    assert "tools" in reg["capabilities"]


def test_load_registries_structure(tmp_path: Path) -> None:
    path = _write_registries(
        tmp_path,
        {
            "modalities": ["audio"],
            "providers": ["openai"],
            "modes": ["chat"],
            "capabilities": ["tools"],
        },
    )
    reg = load_registries(path)
    assert reg["modalities"] == ["audio"]
    assert reg["providers"] == ["openai"]
    assert reg["modes"] == ["chat"]
    assert reg["capabilities"] == ["tools"]


# ── cross_check_vocabulary: passing cases ─────────────────────────────────────


def _reg(
    providers: list[str] | None = None,
    modes: list[str] | None = None,
    capabilities: list[str] | None = None,
    modalities: list[str] | None = None,
) -> Registries:
    return {
        "modalities": modalities or [],
        "providers": providers or ["openai"],
        "modes": modes or ["chat"],
        "capabilities": capabilities or [],
    }


def test_cross_check_passes_on_known_doc() -> None:
    reg = _reg(capabilities=["tools", "vision"])
    doc = _make_doc([_make_model(capabilities=["tools", "vision"])])
    cross_check_vocabulary(doc, reg)  # must not raise


def test_cross_check_passes_empty_models() -> None:
    reg = _reg()
    doc = _make_doc([])
    cross_check_vocabulary(doc, reg)


def test_cross_check_passes_empty_capabilities() -> None:
    reg = _reg()
    doc = _make_doc([_make_model(capabilities=[])])
    cross_check_vocabulary(doc, reg)


# ── cross_check_vocabulary: failure cases ─────────────────────────────────────


def test_cross_check_unknown_provider_raises() -> None:
    reg = _reg(providers=["anthropic"])
    doc = _make_doc([_make_model(provider="openai")])
    with pytest.raises(ValueError, match="unknown provider"):
        cross_check_vocabulary(doc, reg)


def test_cross_check_error_names_provider_value() -> None:
    reg = _reg(providers=["anthropic"])
    doc = _make_doc([_make_model(provider="openai")])
    with pytest.raises(ValueError, match="openai"):
        cross_check_vocabulary(doc, reg)


def test_cross_check_error_names_model_key_for_provider() -> None:
    reg = _reg(providers=["anthropic"])
    doc = _make_doc([_make_model(key="openai:gpt-4o", provider="openai")])
    with pytest.raises(ValueError, match="openai:gpt-4o"):
        cross_check_vocabulary(doc, reg)


def test_cross_check_unknown_mode_raises() -> None:
    reg = _reg(modes=["embedding"])
    doc = _make_doc([_make_model(mode="chat")])
    with pytest.raises(ValueError, match="unknown mode"):
        cross_check_vocabulary(doc, reg)


def test_cross_check_error_names_mode_value() -> None:
    reg = _reg(modes=["embedding"])
    doc = _make_doc([_make_model(mode="chat")])
    with pytest.raises(ValueError, match="chat"):
        cross_check_vocabulary(doc, reg)


def test_cross_check_error_names_model_key_for_mode() -> None:
    reg = _reg(modes=["embedding"])
    doc = _make_doc([_make_model(key="openai:gpt-4o", mode="chat")])
    with pytest.raises(ValueError, match="openai:gpt-4o"):
        cross_check_vocabulary(doc, reg)


def test_cross_check_unknown_capability_raises() -> None:
    reg = _reg(capabilities=["vision"])
    doc = _make_doc([_make_model(capabilities=["unknown_cap"])])
    with pytest.raises(ValueError, match="unknown capability"):
        cross_check_vocabulary(doc, reg)


def test_cross_check_error_names_capability_value() -> None:
    reg = _reg(capabilities=["vision"])
    doc = _make_doc([_make_model(capabilities=["unknown_cap"])])
    with pytest.raises(ValueError, match="unknown_cap"):
        cross_check_vocabulary(doc, reg)


def test_cross_check_error_names_model_key_for_capability() -> None:
    reg = _reg(capabilities=["vision"])
    doc = _make_doc([_make_model(key="openai:gpt-4o", capabilities=["bad_cap"])])
    with pytest.raises(ValueError, match="openai:gpt-4o"):
        cross_check_vocabulary(doc, reg)


# ── cross_check_vocabulary: modality_pricing ─────────────────────────────────


def test_cross_check_passes_known_modality() -> None:
    reg = _reg(modalities=["audio", "image"])
    model = _make_model()
    model["modality_pricing"] = {"audio": {"input_per_million": 32.0}}  # type: ignore[typeddict-unknown-key]
    doc = _make_doc([model])
    cross_check_vocabulary(doc, reg)  # must not raise


def test_cross_check_unknown_modality_raises() -> None:
    reg = _reg(modalities=["audio"])
    model = _make_model()
    model["modality_pricing"] = {"video": {"input_per_million": 1.0}}  # type: ignore[typeddict-unknown-key]
    doc = _make_doc([model])
    with pytest.raises(ValueError, match="unknown modality"):
        cross_check_vocabulary(doc, reg)


def test_cross_check_unknown_modality_names_value() -> None:
    reg = _reg(modalities=["audio"])
    model = _make_model()
    model["modality_pricing"] = {"hologram": {"input_per_million": 1.0}}  # type: ignore[typeddict-unknown-key]
    doc = _make_doc([model])
    with pytest.raises(ValueError, match="hologram"):
        cross_check_vocabulary(doc, reg)


def test_cross_check_unknown_modality_names_model_key() -> None:
    reg = _reg(modalities=["audio"])
    model = _make_model(key="openai:gpt-realtime")
    model["modality_pricing"] = {"hologram": {"input_per_million": 1.0}}  # type: ignore[typeddict-unknown-key]
    doc = _make_doc([model])
    with pytest.raises(ValueError, match="openai:gpt-realtime"):
        cross_check_vocabulary(doc, reg)


# ── real registries file covers all v1 known values ───────────────────────────


def test_real_registries_contains_v03_additions() -> None:
    reg = load_registries(REGISTRIES_PATH)
    for provider in ("glm", "qwen", "minimax", "cerebras", "xai"):
        assert provider in reg["providers"], f"missing provider: {provider}"


def test_real_registries_contains_batch_capability() -> None:
    reg = load_registries(REGISTRIES_PATH)
    assert "batch" in reg["capabilities"]


def test_real_registries_contains_modalities() -> None:
    reg = load_registries(REGISTRIES_PATH)
    assert "audio" in reg["modalities"]
    assert "image" in reg["modalities"]
    assert "video" in reg["modalities"]
