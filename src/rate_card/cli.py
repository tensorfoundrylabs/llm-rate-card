import json
from pathlib import Path
from typing import Annotated

import typer

from rate_card.registries import cross_check_vocabulary, load_registries
from rate_card.schema import SchemaValidationError, load_schema, validate_document

app = typer.Typer(help="LLM rate card generator.", add_completion=False)


@app.command()
def generate(
    config: Annotated[Path, typer.Option("--config", help="Path to config.yaml.")] = Path(
        "config.yaml"
    ),
    sources: Annotated[Path, typer.Option("--sources", help="Path to sources.yaml.")] = Path(
        "sources.yaml"
    ),
    whitelist: Annotated[Path, typer.Option("--whitelist", help="Path to whitelist.yaml.")] = Path(
        "whitelist.yaml"
    ),
    schema: Annotated[
        Path | None, typer.Option("--schema", help="Override schema path from config.")
    ] = None,
    previous: Annotated[
        Path | None,
        typer.Option(
            "--previous", help="Path to previous rate-card.json for verified carry-forward."
        ),
    ] = None,
    output: Annotated[Path, typer.Option("--output", help="Output path.")] = Path("rate-card.json"),
    use_fixture: Annotated[
        bool,
        typer.Option("--use-fixture", help="Read from fixture instead of live sources."),
    ] = False,
    version: Annotated[
        str | None, typer.Option("--version", help="Override release version tag.")
    ] = None,
) -> None:
    """Generate the rate card from configured sources."""
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    from rate_card.generate import run

    try:
        doc, divergences = run(
            config_path=config,
            sources_path=sources,
            whitelist_path=whitelist,
            schema_path=schema,
            previous_path=previous,
            output_path=output,
            use_fixture=use_fixture,
            version=version,
        )
    except Exception as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc

    n = len(doc["models"])
    typer.echo(f"wrote {n} models to {output}")
    if divergences:
        typer.echo(
            f"warning: {len(divergences)} price divergences detected - see {output.with_suffix('.divergences.json')}",
            err=True,
        )


@app.command()
def summarise(
    current: Annotated[Path, typer.Argument(help="Path to current rate-card.json.")],
    previous: Annotated[
        Path | None,
        typer.Option(
            "--previous", help="Path to previous rate-card.json. Omit to treat all entries as new."
        ),
    ] = None,
) -> None:
    """Print a markdown summary of changes between two rate-card documents."""
    from rate_card.changelog import format_summary
    from rate_card.changelog import summarise as _summarise

    try:
        with open(current) as fh:
            curr_doc = json.load(fh)
    except FileNotFoundError as exc:
        typer.echo(f"error: file not found: {exc}", err=True)
        raise typer.Exit(1) from exc
    except json.JSONDecodeError as exc:
        typer.echo(f"error: invalid JSON: {exc}", err=True)
        raise typer.Exit(1) from exc

    prev_doc: dict[str, object] | None = None
    if previous is not None:
        try:
            with open(previous) as fh:
                prev_doc = json.load(fh)
        except FileNotFoundError as exc:
            typer.echo(f"error: file not found: {exc}", err=True)
            raise typer.Exit(1) from exc
        except json.JSONDecodeError as exc:
            typer.echo(f"error: invalid JSON: {exc}", err=True)
            raise typer.Exit(1) from exc

    summary = _summarise(prev_doc, curr_doc)
    typer.echo(format_summary(summary))


@app.command()
def validate(
    path: Annotated[Path, typer.Argument(help="Path to rate-card.json to validate.")],
    schema: Annotated[Path, typer.Option("--schema", help="Path to schema.")] = Path(
        "schema/v1/schema.json"
    ),
    registries: Annotated[
        Path, typer.Option("--registries", help="Path to registries.json.")
    ] = Path("schema/v1/registries.json"),
) -> None:
    """Validate a rate-card.json against the schema and registries."""
    try:
        schema_doc = load_schema(schema)
    except FileNotFoundError as exc:
        typer.echo(f"error: schema not found: {exc}", err=True)
        raise typer.Exit(1) from exc

    try:
        with open(path) as fh:
            doc = json.load(fh)
    except FileNotFoundError as exc:
        typer.echo(f"error: file not found: {exc}", err=True)
        raise typer.Exit(1) from exc
    except json.JSONDecodeError as exc:
        typer.echo(f"error: invalid JSON: {exc}", err=True)
        raise typer.Exit(1) from exc

    try:
        validate_document(doc, schema_doc)
    except SchemaValidationError as exc:
        typer.echo(f"validation failed: {exc}", err=True)
        for error in exc.errors:
            typer.echo(f"  - {error}", err=True)
        raise typer.Exit(1) from exc

    try:
        reg = load_registries(registries)
        cross_check_vocabulary(doc, reg)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"registries check failed: {exc}", err=True)
        raise typer.Exit(1) from exc

    typer.echo(f"{path}: valid")
