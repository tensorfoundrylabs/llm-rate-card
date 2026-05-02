import textwrap
from pathlib import Path

import pytest

from rate_card.config import Config, load_config


def write_config(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent(content))
    return p


def test_load_config_valid(tmp_path: Path) -> None:
    cfg_path = write_config(
        tmp_path,
        """
        litellm_url: "https://example.com/prices.json"
        schema_path: "schema/v1/schema.json"
        divergence_threshold: 0.20
        """,
    )
    cfg = load_config(cfg_path)
    assert isinstance(cfg, Config)
    assert cfg.litellm_url == "https://example.com/prices.json"
    assert cfg.schema_path == "schema/v1/schema.json"
    assert cfg.divergence_threshold == pytest.approx(0.20)


def test_load_config_missing_key(tmp_path: Path) -> None:
    cfg_path = write_config(
        tmp_path,
        """
        litellm_url: "https://example.com/prices.json"
        schema_path: "schema/v1/schema.json"
        """,
    )
    with pytest.raises(ValueError, match="divergence_threshold"):
        load_config(cfg_path)


def test_load_config_threshold_out_of_range(tmp_path: Path) -> None:
    cfg_path = write_config(
        tmp_path,
        """
        litellm_url: "https://example.com/prices.json"
        schema_path: "schema/v1/schema.json"
        divergence_threshold: 1.5
        """,
    )
    with pytest.raises(ValueError, match="divergence_threshold"):
        load_config(cfg_path)


def test_load_config_threshold_zero(tmp_path: Path) -> None:
    cfg_path = write_config(
        tmp_path,
        """
        litellm_url: "https://example.com/prices.json"
        schema_path: "schema/v1/schema.json"
        divergence_threshold: 0.0
        """,
    )
    with pytest.raises(ValueError, match="divergence_threshold"):
        load_config(cfg_path)
