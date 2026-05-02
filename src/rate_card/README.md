# Pipeline

The Python package that produces `rate-card.json` from upstream sources.

## Flow

```
sources.yaml -> fetch -> transform -> merge -> filter -> verified carry-forward -> validate -> hash -> write
```

| Step | Module | What it does |
|---|---|---|
| fetch + transform | `sources/<name>.py` | Each source pulls its upstream and emits `PartialEntry` items in our canonical shape. The rest of the pipeline never sees source-specific field names. |
| merge | `merge.py` | Overlays partial entries by `key` in registry order. Primary supplies the base, secondaries override fields where present. Records divergences when a secondary's price differs from the primary by more than the configured threshold. |
| filter | `filter.py` | Keeps only entries whose `key` is in `whitelist.yaml`. Logs whitelist entries with no matching source data. |
| carry forward | `generate.py` | If `--previous` is supplied, copies `verified` dates from the previous artefact for entries whose prices have not changed. |
| validate | `schema.py` | Validates the assembled document against `schema/v1/schema.json`. Raises on any mismatch. |
| hash | `hashing.py` | SHA-256 over the canonicalised `models` array. Drives release-if-changed: identical hash means no new release. |
| write | `generate.py` | Writes the artefact and, if any divergences were recorded, a sibling `*.divergences.json`. |

## Modules

| File | Responsibility |
|---|---|
| `cli.py` | Typer entry. `rate-card generate`, `rate-card validate`. |
| `generate.py` | Orchestration. Knows nothing source-specific. |
| `sources/base.py` | `Source` Protocol and registry loader. |
| `sources/litellm.py` | LiteLLM-specific fetch and transform. All LiteLLM details live here. |
| `filter.py` | Whitelist application. |
| `merge.py` | Multi-source overlay and divergence detection. |
| `schema.py` | Load and validate against the JSON Schema. |
| `hashing.py` | Canonical content hash. |
| `changelog.py` | Format release notes (one-liner with GitHub compare URL). |
| `config.py` | Parse `config.yaml`. |
| `types.py` | TypedDicts mirroring the schema. |

## Adding a source

A source is a class implementing the `Source` Protocol. Drop a new module under `sources/` and add an entry to `sources.yaml`. No edits to `generate.py`, `merge.py`, or anything downstream.

```python
class MySource:
    name = "my-source"
    role = "secondary"
    enabled = True

    def fetch(self) -> Any: ...
    def transform(self, raw: Any) -> Iterable[PartialEntry]: ...
```

Secondary sources should populate only the fields they have authority over. The merge step composes them with the primary entry. If a secondary supplies a price that differs from the primary by more than `divergence_threshold` (in `config.yaml`), it is recorded in `*.divergences.json` rather than silently overwriting.

## Running

```bash
make pipeline                                              # fixture run, writes .cache/rate-card.json
uv run rate-card generate --output dist/rate-card.json     # live fetch (release path)
uv run rate-card validate dist/rate-card.json
uv run rate-card --help
```

`.cache/` holds local dev output. `dist/` holds the release artefact (what the workflow attaches to a GitHub release). Both are gitignored.

`--use-fixture` forces every source to read from `tests/fixtures/litellm-snapshot.json` instead of the network. Useful for local iteration.

`--previous path/to/old.json` enables `verified` carry-forward.

## Tests

```bash
make test           # all tests
make test-cover     # with coverage report -> htmlcov/
```

Tests are offline-first. The HTTP fetch path in `sources/litellm.py` is the one uncovered area; everything else runs against fixtures.
