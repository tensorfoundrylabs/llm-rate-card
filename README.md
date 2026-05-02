# LLM Rate Card

A daily-curated, signed JSON artefact of per-model pricing and capability metadata for the LLM provider ecosystem. Built for [TensorFoundry](https://tensorfoundry.io)'s products (notably [Alloy]([https](http://tensorfoundry.io/products/)), our LLM gateway) and published openly so anyone else can use it too.

## What's in the box

A single `rate-card.json` per release, attached to a GitHub release tag. Contents:

- Per-model input, output, cache read, cache write, and reasoning prices (per 1M tokens)
- Above-threshold pricing tiers for long-context models
- Context window, max output tokens, capability flags (vision, tools, structured output, etc.)
- Provenance: which sources contributed, when a maintainer last verified the entry

## Schema

The schema is versioned independently of releases. Each version lives in its own directory.

| Version | Status | Schema | Example | README |
|---|---|---|---|---|
| v1 | draft | [schema.json](./schema/v1/schema.json) | [example.json](./schema/v1/example.json) | [readme.md](./schema/v1/README.md) |

See the [authoring guide](./schema/README.md) for how to edit the schema or cut a new version.

## Why this exists

LLM gateways need accurate per-token pricing for cost calculation and budget enforcement. 

We utilise [LiteLLM's `model_prices_and_context_window.json`](https://github.com/BerriAI/litellm) as the base primary source feeding this artefact, but enhance it with secondary scrapers, divergence detection between sources and human-reviewed curation of a focused whitelist of high-frequency-of-use models.

## How to use it

Grab the latest release artefact:

```bash
curl -L https://github.com/tensorfoundrylabs/llm-rate-card/releases/latest/download/rate-card.json -o rate-card.json
```

Verify the Sigstore signature against the `tensorfoundrylabs` GitHub identity (instructions to follow in a later release).

Look up a model by `<provider>:<model_id>`:

```python
import json
card = json.load(open("rate-card.json"))
by_key = {m["key"]: m for m in card["models"]}
entry = by_key["anthropic:claude-sonnet-4-6"]
cost = (input_tokens * entry["input_per_million"] + output_tokens * entry["output_per_million"]) / 1_000_000
```

## Releases

Calendar-versioned tags: `yyyy.mm.dd`, with `-N` suffix for same-day reissues. A release is cut only when the canonical content has actually changed — automated runs that produce no diff do not tag.

Each release attaches `rate-card.json`, a Sigstore signature and certificate, and a CHANGELOG snippet describing what moved.

## Contributing

PRs welcome for whitelist additions, scraper fixes, and schema feedback. For schema changes, read the [authoring guide](./schema/README.md) first.

## Attribution

Primary data is derived from [LiteLLM](https://github.com/BerriAI/litellm) (MIT). The artefact carries this attribution in its `attribution` field so downstream consumers inherit it.

## Licence

MIT. See [LICENSE](./LICENSE).
