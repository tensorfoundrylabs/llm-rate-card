# LLM Rate Card

A daily-curated JSON artefact of per-model pricing and capability metadata for the LLM provider ecosystem. Built for [TensorFoundry](https://tensorfoundry.io)'s products (notably [Alloy](https://tensorfoundry.io/products/), our LLM gateway) and published openly so anyone else can use it too.

## Schema

`v1.0.0` is published. Future versions live in sibling directories.

| Version | Status | Schema | Example | Notes |
|---|---|---|---|---|
| v1 | published | [schema.json](./schema/v1/schema.json) | [example.json](./schema/v1/example.json) | [v1/README.md](./schema/v1/README.md) |

`provider`, `mode`, and `capabilities` are open snake_case patterns. Canonical known values live in [`schema/v1/registries.json`](./schema/v1/registries.json) and the pipeline cross-checks every emitted value against that file. See the [authoring guide](./schema/README.md) for how to edit the schema or cut a new version.

## What's in each release

A single `rate-card.json` attached to a calver tag (`yyyy.mm.dd`, `-N` suffix for same-day reissues). Per-model fields:

- Input, output, cache read, cache write, and reasoning prices (per 1M tokens)
- `modality_pricing` for multi-modal models (per-modality rates for audio, image, video alongside the text default)
- Above-threshold pricing tiers for long-context models
- Context window, max output tokens, capability flags
- Provenance: which sources contributed, when a maintainer last verified the entry

A release is cut only when the canonical content actually changes. Automated runs that produce no diff do not tag.

## Example entry

```json
{
  "key": "openai:gpt-realtime-1.5",
  "provider": "openai",
  "model_id": "gpt-realtime-1.5",
  "mode": "chat",
  "input_per_million": 4.0,
  "output_per_million": 16.0,
  "cache_read_per_million": 0.4,
  "context_window": 32000,
  "max_output_tokens": 4096,
  "capabilities": ["streaming", "tools", "audio_input", "audio_output"],
  "modality_pricing": {
    "audio": { "input_per_million": 32.0, "output_per_million": 64.0, "cache_read_per_million": 0.4 },
    "image": { "input_per_million": 5.0, "cache_read_per_million": 0.5 }
  },
  "verified": "2026-05-03",
  "sources": ["litellm", "openai-direct"],
  "source_url": "https://developers.openai.com/api/docs/pricing"
}
```

Top-level fields (`input_per_million` etc.) carry the text rate. Non-text modalities live in `modality_pricing`. The `sources` array lists every contributor; `source_url` is the canonical pricing page.

## How to consume

Grab the latest release artefact:

```bash
curl -L https://github.com/tensorfoundrylabs/llm-rate-card/releases/latest/download/rate-card.json -o rate-card.json
```

Look up a model by `<provider>:<model_id>`:

```python
import json
card = json.load(open("rate-card.json"))
by_key = {m["key"]: m for m in card["models"]}
entry = by_key["anthropic:claude-sonnet-4-6"]
cost = (input_tokens * entry["input_per_million"] + output_tokens * entry["output_per_million"]) / 1_000_000
```

For multi-modal models, fall back to `modality_pricing[modality]` when present, else top-level (text).

## Sources

[LiteLLM](https://github.com/BerriAI/litellm) is the primary source. Direct scrapers overlay where they have authority and divergence detection flags disagreements rather than silently overwriting. Currently scraping: Anthropic, OpenAI, Mistral, GLM, MiniMax, Groq, xAI, Cerebras, Qwen.

## Pipeline

A daily GitHub Action fetches every enabled source, merges with divergence detection, validates against the schema and registries, and tags a release only when content changes.

Local development:

```bash
make install        # install deps
make ready          # fmt + lint + lint-yaml + type-check + test
make pipeline       # run against the fixture, write to .cache/
uv run rate-card --help
```

See [`src/rate_card/README.md`](./src/rate_card/README.md) for pipeline structure and how to add a source.

## Contributing

PRs welcome for whitelist additions, scraper fixes, and schema feedback. For schema changes, read the [authoring guide](./schema/README.md) first.

## Attribution

Primary data derived from [LiteLLM](https://github.com/BerriAI/litellm) (MIT). The artefact carries this attribution in its `attribution` field so downstream consumers inherit it.

## Licence

MIT. See [LICENSE](./LICENSE).
