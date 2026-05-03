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
| cross-check | `registries.py` | Verifies every provider, mode, capability, and modality_pricing key in the document is listed in `schema/v1/registries.json`. Fails loudly on any unknown value. |
| hash | `hashing.py` | SHA-256 over the canonicalised `models` array. Drives release-if-changed: identical hash means no new release. |
| write | `generate.py` | Writes the artefact and, if any divergences were recorded, a sibling `*.divergences.json`. |

## Modules

| File | Responsibility |
|---|---|
| `cli.py` | Typer entry. `rate-card generate`, `rate-card validate`. |
| `generate.py` | Orchestration. Knows nothing source-specific. |
| `sources/base.py` | `Source` Protocol and registry loader. |
| `sources/litellm.py` | LiteLLM-specific fetch and transform. All LiteLLM details live here. |
| `sources/_http.py` | Shared HTTP fetch helper used by all sources. |
| `sources/_normalise.py` | Shared numeric helpers (round_per_million). |
| `sources/_scraper.py` | `BaseScraper` template-method base for secondary HTML scrapers. |
| `registries.py` | Load `registries.json` and cross-check vocabulary against it. |
| `filter.py` | Whitelist application. |
| `merge.py` | Multi-source overlay and divergence detection. |
| `schema.py` | Load and validate against the JSON Schema. |
| `hashing.py` | Canonical content hash. |
| `changelog.py` | Format release notes (one-liner with GitHub compare URL). |
| `config.py` | Parse `config.yaml`. |
| `types.py` | TypedDicts mirroring the schema. |

## Adding a source

There are two patterns.

### Primary source

There is currently one primary source: LiteLLM. A primary source is a custom class that transforms a rich upstream format (JSON, etc.) into `PartialEntry` items. It uses `sources/_http.fetch_text` for fetching and `sources/_normalise.round_per_million` for price conversion. Set `role = "primary"` and register it in `sources.yaml`.

### Secondary scraper

Secondary sources overlay the primary's data with prices scraped directly from a provider's pricing page. Extend `BaseScraper` from `sources/_scraper.py`, set the four class variables, and implement `_extract`:

```python
from rate_card.sources._scraper import BaseScraper, ScrapedRow

class AcmeSource(BaseScraper):
    name = "acme"
    provider = "acme"
    url = "https://acme.example.com/pricing"

    def _extract(self, raw: str) -> Iterable[ScrapedRow]:
        # parse raw HTML, yield ScrapedRow dicts
        ...
```

`BaseScraper._row_to_entry` handles setting `key`, `provider`, `sources`, `source_url`, and rounding all numeric fields. Do not set `mode`, `capabilities`, `context_window`, or other primary-owned fields -- those come from the primary source via merge.

Add the class to `sources.yaml` with `role: secondary`. The merge step composes it with the primary entry and records price divergences exceeding `divergence_threshold`.

### Open-vocabulary constraint

Emitting a new `provider` value in any source also requires adding that value to `schema/v1/registries.json`. The pipeline's cross-check step fails loudly if an unknown value reaches the final document. This applies to `mode` and `capabilities` values too.

## Field reference: modality_pricing

Multi-modal models (such as OpenAI's Realtime and image-generation models) publish separate token rates for different input types. The `modality_pricing` field holds these as a dict keyed by modality name (`audio`, `image`, `video`).

The top-level `input_per_million`, `output_per_million`, and cache fields always carry **text** rates and are the canonical default. `modality_pricing` holds non-text rates only; `text` is never a key. Each value has the shape `{input_per_million, output_per_million?, cache_read_per_million?, cache_write_per_million?}`. The merge step deep-merges per-modality keys from secondary sources so a secondary supplying `image` rates does not erase `audio` rates already present from an earlier source. Consumers that encounter an unknown modality key should fall back to top-level text rates.

## Running

```bash
make pipeline                                              # fixture run, writes .cache/rate-card.json
uv run rate-card generate --output dist/rate-card.json     # live fetch (release path)
uv run rate-card validate dist/rate-card.json
uv run rate-card --help
```

`.cache/` holds local dev output. `dist/` holds the release artefact (what the workflow attaches to a GitHub release). Both are gitignored.

Each GitHub release includes both `rate-card.json` and `rate-card.json.gz`. The gz artefact is preferred for binary embedding (Go `//go:embed`, Docker layer baking, and similar) where download size matters. Both carry identical content; `content_hash` in the JSON is the authoritative identity signal.

`--use-fixture` forces every source to read from `tests/fixtures/litellm-snapshot.json` instead of the network. Useful for local iteration.

`--previous path/to/old.json` enables `verified` carry-forward.

## Tests

```bash
make test           # all tests
make test-cover     # with coverage report -> htmlcov/
```

Tests are offline-first. `pytest-httpx` mocks all HTTP requests. The fixture at `tests/fixtures/litellm-snapshot.json` is the primary data source for most tests.
