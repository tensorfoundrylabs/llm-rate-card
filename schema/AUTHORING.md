# Schema authoring guide

For anyone editing the schema or cutting a new version. Consumers should read the version's own README.

## Directory shape

Every version is a directory `schema/vN/` containing:

| File | Purpose |
|---|---|
| `schema.json` | the JSON Schema (draft 2020-12) |
| `example.json` | a sample document that validates against `schema.json` |
| `registries.json` | canonical vocabulary lists for provider, mode, and capability |
| `registries.schema.json` | meta-schema validating `registries.json` |
| `README.md` | what this version is, key design choices, change history |

CI rejects PRs where any of these is missing, where the example fails schema validation, or where `registries.json` fails its own meta-schema validation.

## When to bump

Decide before opening the PR.

| Bump | Trigger | Where to edit |
|---|---|---|
| Patch (`1.0.0` -> `1.0.1`) | description text, typo fixes, no behaviour change | in place |
| Minor (`1.0.0` -> `1.1.0`) | additive only: new optional field, new enum member, looser constraint | in place, bump `schema_version` in example, add a row to the version's change history |
| Major (`1.x.x` -> `2.0.0`) | anything that can invalidate a previously valid document: required field added or removed, enum member removed, field renamed or retyped | copy directory to `vN+1/`, edit there, leave the old version untouched |

Adding a value to `registries.json` does NOT bump the schema version. It is vocabulary data, not a contract change. The schema pattern already accepts the new value; only the pipeline's cross-check is affected.

Old major versions are never edited after a successor ships. Released artefacts pin to a specific schema URL and must keep validating forever.

## Identifier convention

`$id` follows `https://schema.tensorfoundry.io/rate-card/vN/schema.json`. The path mirrors the repo path. The URL is an identifier, not a fetch target. Do not change it once published.

## Validating locally

```bash
uvx check-jsonschema --schemafile schema/v1/schema.json schema/v1/example.json
```

The `validate-schemas` workflow runs this against every `schema/vN/` directory on PRs that touch `schema/`.
