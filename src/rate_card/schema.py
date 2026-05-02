import json
from pathlib import Path
from typing import Any

import jsonschema
import jsonschema.exceptions


def load_schema(path: str | Path) -> dict[str, Any]:
    """Load a JSON Schema from disk."""
    with open(path) as fh:
        return json.load(fh)  # type: ignore[no-any-return]


class SchemaValidationError(Exception):
    """Raised when a document fails schema validation."""

    def __init__(self, message: str, errors: list[str]) -> None:
        super().__init__(message)
        self.errors = errors


def validate_document(doc: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate doc against schema, raising SchemaValidationError on failure."""
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        messages = [f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors]
        raise SchemaValidationError(
            f"{len(errors)} validation error(s)",
            messages,
        )
