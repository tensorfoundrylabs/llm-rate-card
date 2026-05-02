# Working notes for Claude

Project conventions and orientation. Read this before doing anything substantive.

## What this repo is

Public, MIT-licensed pipeline that produces `rate-card.json`: per-model LLM pricing and capability metadata. LiteLLM is the primary source; secondary scrapers will land in v0.3+.

The schema is the contract. Output validates against `schema/v1/schema.json`.

## Style (hard rules)

- **Australian English** in every word produced: organise, behaviour, licence, colour, optimise, artefact, recognise. Applies to docs, code comments, docstrings, commit messages, log messages, error strings.
- **No em-dashes anywhere.** Use hyphens, commas, or restructure.
- **No AI prose tells.** No "let me", "I'll help", "Certainly!", no breathless adjectives ("comprehensive", "robust", "powerful", "seamless"), no "in summary" wrap-ups, no decorative emojis.
- **Default to no code comments.** Only comment when WHY is non-obvious. Never restate WHAT the code does. Never reference current task or PR.
- **Docstrings**: one line, public APIs only. No multi-paragraph docstrings.
- **Commits**: short, lowercase, imperative, human. No bullet-list bodies. No `Co-Authored-By: Claude` or any AI signature.

## Architectural rules

- **Sources are self-contained.** Each `sources/<name>.py` fetches and transforms into our `PartialEntry` shape. The rest of the pipeline never sees upstream-specific fields. New source = new module + entry in `sources.yaml`. Never plumb source-specifics into `generate.py`, `merge.py`, etc.
- **The schema is the contract.** Don't add fields to the artefact without a schema change. Don't add a runtime model layer (no pydantic) — `TypedDict` mirrors the schema, the JSON Schema validator is the runtime check.
- **Schema versioning.** `schema/v1/` is locked once a successor exists. New majors copy to `schema/v2/`. Per-version README captures change history. See `schema/AUTHORING.md`.
- **No backwards-compat shims.** Nothing has shipped publicly yet.
- **No defensive code for impossible cases.** Trust internal callers. Validate at boundaries (parsing source data, parsing config, validating final output).

## Tooling

- Python 3.12, uv for everything. Build backend is `uv_build` (not hatchling).
- `ruff` strict, `mypy` strict, `pytest` with `--cov-fail-under=90`.
- `make ready` is the pre-commit gate: `fmt + lint + type-check + test`. It must be green before any change is considered done.

## Common commands

| Command | What |
|---|---|
| `make install` | Install runtime + dev deps |
| `make ready` | Pre-commit gate |
| `make pipeline` | Run pipeline against fixture, write `dist/rate-card.json` |
| `make ci` | Full check |
| `uv run rate-card generate --use-fixture --output dist/rate-card.json` | Local pipeline run |
| `uv run rate-card validate dist/rate-card.json` | Validate an artefact |
| `uvx check-jsonschema --schemafile schema/v1/schema.json schema/v1/example.json` | Validate the schema example |

## Layout

```
schema/v1/                 schema, example, version README
src/rate_card/             pipeline (see src/rate_card/README.md)
tests/                     pytest, fixtures under tests/fixtures/
.github/workflows/         CI: validate-schemas.yml, build-rate-card.yml
sources.yaml               source registry
config.yaml                runtime config (divergence threshold, schema path)
whitelist.yaml             curated ~70-90 model list
```

## Testing

Tests are offline-first. Live HTTP is not exercised in the suite. The fixture at `tests/fixtures/litellm-snapshot.json` covers tiered pricing, cache write/read split, deprecation date, prefix stripping, audio capabilities, embedding mode, and reasoning-token pricing.

If you add a transform branch, add a fixture entry that exercises it and a test that asserts the branch.

## When extending

| Task | Where it goes |
|---|---|
| Adding a new source | New `src/rate_card/sources/<name>.py` + entry in `sources.yaml` + tests under `tests/test_sources_<name>.py` |
| Changing the schema | `schema/AUTHORING.md` defines the rules. Decide patch vs minor vs major before editing. |
| Adding a capability or provider enum value | Schema change (minor bump if additive). Update mapping in `sources/litellm.py`. |
| Adding a config knob | `config.yaml` + `config.py` dataclass + tests |
| Adding a CLI flag | `cli.py`, plumb into `generate.run()` |

## Don'ts

- Don't auto-publish a release if scrapers diverge significantly. Divergence is logged to `*.divergences.json` for human review.
- Don't modify `schema/v1/schema.json` after a successor ships.
- Don't add `pydantic`, `attrs`, or other runtime-validation layers. The JSON Schema validator is the runtime check.
- Don't write tests that hit the network. Use fixtures.
- Don't commit `.coverage`, `dist/`, `htmlcov/`, or any `__pycache__/`.

## Memory

User-level conventions (writing style, comments policy, commit style) are saved in `~/.claude/projects/D--projects-tensorfoundry-llm-rate-card/memory/`. They mirror the rules above.
