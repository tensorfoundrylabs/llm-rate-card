import json
import textwrap
from pathlib import Path

from typer.testing import CliRunner

from rate_card.cli import app

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "litellm-snapshot.json"
CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
SOURCES_PATH = Path(__file__).parent.parent / "sources.yaml"
SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "v1" / "schema.json"

runner = CliRunner()


def _whitelist(tmp_path: Path) -> Path:
    p = tmp_path / "whitelist.yaml"
    p.write_text(
        textwrap.dedent("""
        openai:
          - gpt-4o
        anthropic:
          - claude-sonnet-4-5
    """)
    )
    return p


def test_generate_with_fixture(tmp_path: Path) -> None:
    wl = _whitelist(tmp_path)
    output = tmp_path / "rate-card.json"
    result = runner.invoke(
        app,
        [
            "generate",
            "--config",
            str(CONFIG_PATH),
            "--sources",
            str(SOURCES_PATH),
            "--whitelist",
            str(wl),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output),
            "--use-fixture",
        ],
    )
    assert result.exit_code == 0, result.output
    assert output.exists()
    assert "wrote 2 models" in result.output


def test_generate_output_is_valid_json(tmp_path: Path) -> None:
    wl = _whitelist(tmp_path)
    output = tmp_path / "rate-card.json"
    runner.invoke(
        app,
        [
            "generate",
            "--config",
            str(CONFIG_PATH),
            "--sources",
            str(SOURCES_PATH),
            "--whitelist",
            str(wl),
            "--output",
            str(output),
            "--use-fixture",
        ],
    )
    with open(output) as fh:
        doc = json.load(fh)
    assert doc["name"] == "TensorFoundry LLM Rate Card"
    assert len(doc["models"]) == 2


def test_generate_missing_whitelist_fails(tmp_path: Path) -> None:
    output = tmp_path / "rate-card.json"
    result = runner.invoke(
        app,
        [
            "generate",
            "--config",
            str(CONFIG_PATH),
            "--sources",
            str(SOURCES_PATH),
            "--whitelist",
            str(tmp_path / "nonexistent.yaml"),
            "--output",
            str(output),
            "--use-fixture",
        ],
    )
    assert result.exit_code == 1


def test_validate_valid_file(tmp_path: Path) -> None:
    wl = _whitelist(tmp_path)
    output = tmp_path / "rate-card.json"
    runner.invoke(
        app,
        [
            "generate",
            "--config",
            str(CONFIG_PATH),
            "--sources",
            str(SOURCES_PATH),
            "--whitelist",
            str(wl),
            "--output",
            str(output),
            "--use-fixture",
        ],
    )
    result = runner.invoke(
        app,
        ["validate", str(output), "--schema", str(SCHEMA_PATH)],
    )
    assert result.exit_code == 0
    assert "valid" in result.output


def test_validate_invalid_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json")
    result = runner.invoke(
        app,
        ["validate", str(bad), "--schema", str(SCHEMA_PATH)],
    )
    assert result.exit_code == 1


def test_validate_file_not_found(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["validate", str(tmp_path / "missing.json"), "--schema", str(SCHEMA_PATH)],
    )
    assert result.exit_code == 1


def test_validate_schema_not_found(tmp_path: Path) -> None:
    wl = _whitelist(tmp_path)
    output = tmp_path / "rate-card.json"
    runner.invoke(
        app,
        [
            "generate",
            "--config",
            str(CONFIG_PATH),
            "--sources",
            str(SOURCES_PATH),
            "--whitelist",
            str(wl),
            "--output",
            str(output),
            "--use-fixture",
        ],
    )
    result = runner.invoke(
        app,
        ["validate", str(output), "--schema", str(tmp_path / "missing-schema.json")],
    )
    assert result.exit_code == 1


def test_validate_fails_on_invalid_document(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    with open(bad, "w") as fh:
        json.dump({"name": "not a rate card"}, fh)
    result = runner.invoke(
        app,
        ["validate", str(bad), "--schema", str(SCHEMA_PATH)],
    )
    assert result.exit_code == 1
