# Rate Card schema v1

Initial release. Modelled on Alloy v2 - v3, with changes for Alloy v4.

JSON Schema draft 2020-12. `$id`: `https://schema.tensorfoundry.io/rate-card/v1/schema.json`.

A document has a metadata block at the top and a flat `models` array. Lookup is by the per-model `key` field, formatted `<provider>:<model_id>`.

## Top-level fields

| Field | Purpose |
|---|---|
| `schema_version` | semver of the schema this document conforms to |
| `name`, `author` | const-locked to TensorFoundry's identifiers |
| `homepage`, `license`, `license_url`, `attribution` | provenance and licence carry-through for downstream consumers |
| `currency` | ISO 4217 code. All per-million figures in the document are denominated in this currency |
| `release` | version, generation timestamp, source commit, signature URL |
| `content_hash` | SHA-256 over the canonicalised `models` array. Drives release-if-changed semantics |
| `models` | per-model entries |

## Per-model fields

| Field | Purpose |
|---|---|
| `key` | stable lookup key, `<provider>:<model_id>` |
| `provider`, `model_id`, `mode` | provider enum, native API identifier, mode enum (chat, embedding, ...) |
| `input_per_million`, `output_per_million` | base rates (text modality) |
| `cache_read_per_million`, `cache_write_per_million` | nullable, kept separate so providers that price reads and writes differently are represented honestly |
| `reasoning_per_million` | nullable, for o-series and extended-thinking models |
| `pricing_tiers` | optional, above-threshold rates for long-context models |
| `modality_pricing` | optional, per-modality rates for multi-modal models (see below) |
| `context_window`, `max_output_tokens` | input and output limits |
| `capabilities` | enum array (vision, tools, structured_output, prompt_caching, ...) |
| `deprecation_date` | nullable ISO date if the provider has announced a sunset |
| `verified` | ISO date a maintainer last confirmed the entry against the provider's pricing page |
| `sources`, `source_url` | source identifiers and an optional traceability link |

The schema's own `description` fields are the authoritative reference. This README captures intent.

## Design Choices

### Currency Handling

We've included a `currency` field (top-level) which allows easy conversion without field issues (Eg. `currency:aud` and all fields are AUD).

### Content Hash

The `content_hash` is for the `models` component only by design, this means two releases with identical models will give us the same hash regardless of meta fields.

### No Additional Properties

We've disabled `additionalProperties` everywhere to catch unknown silent field propagation.han silently propagating. |

## Vocabularies

`provider`, `mode`, and `capabilities[items]` are open-pattern fields: the schema accepts any `snake_case` identifier matching `^[a-z][a-z0-9_]*$`. The canonical known values are maintained in `registries.json` alongside this file.

The pipeline cross-checks every value in a generated document against `registries.json` and fails loudly on any unknown value. Adding a new provider, mode, or capability therefore requires both a code change (the source emitting the value) and a `registries.json` update.

The meta-schema for `registries.json` is `registries.schema.json`. CI validates both the rate-card example and the registries file on every schema-touching PR.

### modality_pricing

Some providers publish separate token rates per input modality (audio, image, video). The `modality_pricing` field captures these as a map keyed by modality name. Keys must appear in `registries.modalities`; the `text` modality is never a key here because text rates are the top-level default (`input_per_million`, `output_per_million`, etc.). Each value has the same shape as a pricing tier (`input_per_million` required, `output_per_million`, `cache_read_per_million`, and `cache_write_per_million` optional). Consumers that do not recognise a modality key should fall back to the top-level text rates rather than treating the model as unpriced.

## Change history

| Date | Version | Change | Author | Company
|---|---|---|---|---|
| unreleased | 1.0.0 | initial; open-vocabulary refactor; registries.json introduced | Thushan Fernando | TensorFoundry
| 2026-05-02 | 1.0.0 | add modality_pricing field and modalities registry vocabulary | Thushan Fernando | TensorFoundry
| 2026-05-02 | 1.0.0 | make context_window and output_per_million optional; image-generation models have pixel-based input and no token-denominated output | Thushan Fernando | TensorFoundry
