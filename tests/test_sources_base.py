import textwrap
from pathlib import Path

import pytest

from rate_card.sources.base import Source, load_sources
from rate_card.sources.litellm import LiteLLM, _build_capabilities


def write_sources_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "sources.yaml"
    p.write_text(textwrap.dedent(content))
    return p


def test_load_sources_litellm(tmp_path: Path) -> None:
    p = write_sources_yaml(
        tmp_path,
        """
        - module: rate_card.sources.litellm
          class: LiteLLM
          name: litellm
          role: primary
          enabled: true
          url: "https://example.com/prices.json"
        """,
    )
    sources = load_sources(p)
    assert len(sources) == 1
    assert isinstance(sources[0], LiteLLM)
    assert sources[0].name == "litellm"


def test_load_sources_disabled_skipped(tmp_path: Path) -> None:
    p = write_sources_yaml(
        tmp_path,
        """
        - module: rate_card.sources.litellm
          class: LiteLLM
          name: litellm
          role: primary
          enabled: false
          url: "https://example.com/prices.json"
        """,
    )
    sources = load_sources(p)
    assert sources == []


def test_load_sources_unknown_module_raises(tmp_path: Path) -> None:
    p = write_sources_yaml(
        tmp_path,
        """
        - module: rate_card.sources.does_not_exist
          class: SomeClass
          name: test
          role: primary
          enabled: true
          url: "https://example.com"
        """,
    )
    with pytest.raises(ModuleNotFoundError):
        load_sources(p)


def test_source_protocol_not_implemented() -> None:
    s = Source()
    with pytest.raises(NotImplementedError):
        s.fetch()
    with pytest.raises(NotImplementedError):
        list(s.transform({}))


def test_build_capabilities_unexpected_value_ignored() -> None:
    # non-True truthy value for a known capability field - should not raise
    caps = _build_capabilities({"supports_vision": "yes"})
    assert "vision" not in caps
