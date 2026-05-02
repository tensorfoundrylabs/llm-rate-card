import json
from pathlib import Path
from typing import Annotated

import typer

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
def validate(
    path: Annotated[Path, typer.Argument(help="Path to rate-card.json to validate.")],
    schema: Annotated[Path, typer.Option("--schema", help="Path to schema.")] = Path(
        "schema/v1/schema.json"
    ),
) -> None:
    """Validate a rate-card.json against the schema."""
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

    typer.echo(f"{path}: valid")
