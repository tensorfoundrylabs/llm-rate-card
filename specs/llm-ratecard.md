# Project spec: llm-rate-card

## What this is

A public, MIT-licensed GitHub repository at **`github.com/tensorfoundrylabs/llm-rate-card`** that produces a daily-curated, signed JSON artefact containing per-model pricing and capability metadata for the LLM provider ecosystem.

The artefact is the canonical reference rate card consumed by **Alloy** (TensorFoundry's LLM gateway), and is published openly so any other LLM gateway, observability tool, or cost-management product can consume it freely.

The repository contains both the generation pipeline (Python) and the published artefact (JSON, in releases). One repo, generation and output together, deliberately not split.

## Why this exists

### The problem

LLM gateways need accurate per-token pricing to:

- Calculate cost from token usage
- Enforce dollar-denominated budgets
- Show operators "you spent $X this month"
- Compare provider costs for routing decisions

There is no canonical industry source. Each provider publishes prices in their own format on their own pricing page, with regional variations, promotional rates, and inconsistent units (per-1k tokens vs per-1M tokens vs per-character).

### The existing answer

The de-facto industry source today is **LiteLLM's `model_prices_and_context_window.json`** (`github.com/BerriAI/litellm/blob/main/litellm/model_prices_and_context_window_backup.json`). It's MIT-licensed, updated multiple times per week, covers 400+ models. PortKey, OpenRouter, several smaller gateways, and many internal tools derive from it.

LiteLLM is the right base. But it has gaps:

- **Bedrock and Vertex regional pricing** is under-covered (us-east-1 vs eu-west-1 vs ap-southeast-2 differ for some models)
- **Gemini and Claude release cadence** outpaces LiteLLM's updates by days
- **Long-tail providers** (HuggingFace, Replicate marketplaces) are nominally tracked but the data is unreliable because pricing varies per model uploader
- **Capability metadata** (vision, tools, streaming, structured output) is inconsistently populated

### What we add

This repo:

1. Pulls LiteLLM as the base on a daily schedule
2. Filters to a curated **~80-model whitelist** of the highest-frequency-of-use models across the providers Alloy supports
3. **Augments** entries with secondary scrapes for the 6 high-value providers where LiteLLM has known gaps
4. **Detects divergence** between sources and flags suspect entries for human review rather than auto-publishing bad data
5. **Releases** a clean Alloy-format JSON artefact ONLY when content has actually changed
6. **Signs** the release via Sigstore keyless signing (GitHub OIDC) so consumers can verify origin

### Why public

The data has near-zero moat: LiteLLM already gives it away. The moat is the gateway that uses it. Open-sourcing the rate card builds goodwill, attracts community PRs for prices we miss, and signals trustworthiness ("here's where these numbers come from"). TensorFoundry's commercial product (Alloy) is the value-add; the rate card is a public good that happens to be useful to Alloy.

## Domain context: Alloy

Alloy is TensorFoundry's LLM gateway / control plane. It proxies requests to 16 LLM providers (OpenAI, Anthropic, Azure OpenAI, AWS Bedrock, Google Vertex, Google Gemini direct, Ollama, Custom OpenAI-compatible, OpenRouter, DeepSeek, Groq, Perplexity, Mistral, Cohere, HuggingFace, Replicate). It enforces per-team and per-key dollar budgets, tracks usage, and routes across multiple deployments.

Alloy is in a clean-room v4 build, pre-launch, written in Go. The rate card is consumed at runtime to compute per-request cost: `(input_tokens × input_per_million / 1_000_000) + (output_tokens × output_per_million / 1_000_000)`. Without an accurate rate card, budget enforcement is meaningless.

Alloy will embed a snapshot of the rate card in its binary at build time. v1.0 of Alloy ships with whatever the latest llm-rate-card release is at Alloy's release date. v1.1+ may auto-fetch updates via a Console "Update rate card" button, which is why signed releases matter from day one even though v1.0 doesn't auto-fetch.

## Sources and merge strategy

### Primary

**LiteLLM**, pulled from their main branch JSON file. License: MIT. Attribution required in our README.

### Secondary (augment for known gaps)

| Provider | Source type | Purpose |
|---|---|---|
| Anthropic direct | Docs page scrape | Verify LiteLLM is current, fill cache pricing |
| OpenAI | Pricing page scrape | Same |
| AWS Bedrock | Docs page scrape | Regional pricing variations LiteLLM under-covers |
| Google Vertex | Docs page scrape | Same |
| Gemini direct | Docs page scrape | Catches new model launches before LiteLLM |
| OpenRouter | API call (`/api/v1/models`) | Their canonical rate card; aggregates everything they expose |

### Skip entirely

- **Azure OpenAI**: customer-deployment pricing; rate card is a notional reference only
- **DeepSeek, Groq, Perplexity, Mistral, Cohere**: stable providers, LiteLLM is reliable
- **HuggingFace, Replicate**: marketplaces with per-creator pricing; meaningless to maintain a "canonical" rate

### Merge rules

- LiteLLM is the base entry. Secondary sources can *override* fields where they have authoritative data (e.g. Bedrock scraper for regional pricing).
- If a secondary source disagrees with LiteLLM by **>20%** on input or output price, **flag in the generated PR/release notes for human review** rather than auto-publishing. Likely a scraping bug; sometimes a real price change.
- If a secondary source returns no entry but LiteLLM does, keep LiteLLM's entry (don't delete on missing).
- If LiteLLM removes a model that we have in our whitelist, log a Warn but keep the previous entry until manual whitelist update.

### Whitelist

A curated `whitelist.yaml` listing the ~80 models we publish, organised by provider. Frequency-of-use, not breadth. The Alloy session has a starter list already; that goes into this repo as the seed whitelist. Updates happen via PR.

Models NOT on the whitelist are excluded from output, even if LiteLLM has them. Alloy operators handle long-tail models by entering prices manually in the Console.

## Output format

A single JSON artefact, structured for fast lookup by `<provider_type>:<model_id>`. Per-entry fields:

- `key`: the lookup key, e.g. `anthropic:claude-sonnet-4-7`
- `provider`: provider type (matches Alloy's enum: `openai`, `anthropic`, `bedrock`, `vertex`, etc.)
- `model_id`: provider-native model identifier (whatever the provider's API expects)
- `input_per_million_usd`: USD per 1M input tokens
- `output_per_million_usd`: USD per 1M output tokens
- `cached_input_per_million_usd`: optional, USD per 1M cached input tokens
- `context_window`: max context tokens
- `capabilities`: array of strings (`streaming`, `vision`, `tools`, `structured_output`, etc.)
- `verified`: ISO date when this entry was last manually confirmed (carried forward across auto-runs unless price changed)
- `sources`: array of source identifiers contributing to this entry (e.g. `["litellm", "anthropic-direct"]`) for traceability

Top-level metadata:

- `generated_at`: ISO timestamp of generation
- `release_version`: the release tag this artefact corresponds to
- `signature_url`: pointer to the sigstore signature for this release

The exact JSON shape (field naming, nullable conventions) should be agreed with the Alloy team before first release; this spec describes intent, not the schema.

## Release semantics

### When to release

A release is cut **only if the canonical content has changed**. Compute a content hash that excludes the `generated_at` timestamp and the `verified` dates (which churn naturally). If the hash matches the previous release, skip: no new tag, no new artefact.

### Tag format

**`yyyy.mm.dd`** (calendar versioning). If multiple releases happen on the same day, append `-N` (e.g. `2026.05.02-1`, `2026.05.02-2`). ISO-friendly, sorts lexicographically, no ambiguity.

The original suggestion was `yyyy-mm.<release>` (e.g. `2026-05.7`). Either works; calendar versioning is more conventional. Open question to confirm with the user.

### Signing

**Sigstore keyless signing** via the GitHub Actions OIDC token. Adds about 10 lines to the workflow. No GPG key management, no secrets. Signature verifiable against the `tensorfoundrylabs` GitHub identity. Future-proofs the auto-fetch path for Alloy v1.1+.

### Release artefacts

Each GitHub release attaches:

- `rate-card.json`: the canonical artefact
- `rate-card.json.sig`: Sigstore signature
- `rate-card.json.crt`: Sigstore certificate
- `CHANGELOG.md` snippet describing what changed (added/removed/repriced models)

## Repo conventions

- **Python 3.12+**, **uv** for dependency management (TF standard)
- **Linting**: `ruff` for lint and format. Strict by default.
- **Tests**: `pytest`. Cover the merge logic, divergence detection, schema validation, fixture-based scraper tests (don't hit live URLs in CI by default).
- **Pre-commit**: `pre-commit` hooks for ruff, schema validation, whitelist sanity check.
- **CI**: GitHub Actions. Workflows: `test.yml` (on PR), `nightly.yml` (cron), `release.yml` (triggered by nightly when content changes).
- **Australian English** in user-facing docs. No em-dashes. (TF house style.)
- **MIT licence** with attribution to LiteLLM in `LICENSE` and `README`.

## Workflow architecture

A daily cron job in GitHub Actions:

1. Pull latest LiteLLM JSON
2. Run each enabled secondary scraper
3. Filter to whitelist
4. Merge with divergence detection (>20% delta flagged)
5. Validate against schema
6. Compute content hash
7. If hash matches latest release: exit cleanly, no release
8. Else: generate `CHANGELOG.md` snippet from diff, tag release, attach artefacts, sign via Sigstore
9. Post a summary to a designated channel (Slack webhook or GitHub Discussions: TBD)

## Repo layout (proposed)

```
llm-rate-card/
├── README.md                    # What this is, how to use, attribution
├── LICENSE                      # MIT
├── CONTRIBUTING.md              # PR guidelines, how to add a model to whitelist
├── pyproject.toml               # uv-managed
├── src/
│   ├── sources/                 # one module per source
│   ├── filter.py                # whitelist application
│   ├── merge.py                 # source precedence, divergence detection
│   ├── schema.py                # output schema and validation
│   ├── changelog.py             # diff-to-changelog generator
│   └── generate.py              # entry point
├── whitelist.yaml               # the curated 80-model list
├── tests/
│   ├── test_sources.py
│   ├── test_merge.py
│   ├── test_filter.py
│   └── fixtures/                # canned scraper responses
└── .github/
    └── workflows/
        ├── test.yml             # PR validation
        ├── nightly.yml          # cron + diff
        └── release.yml          # tag, sign, publish
```

## Open questions to resolve with the user

1. **Tag format**: `yyyy.mm.dd-N` (recommended) or `yyyy-mm.N` (user's original suggestion)?
2. **Whitelist seeding**: Alloy session has drafted a ~80-model list. Pull from there, or curate fresh?
3. **Divergence threshold**: 20% feels right; user may have a stronger view based on observed price volatility.
4. **Notification channel for releases**: Slack? GitHub Discussions? Both?
5. **Schema review with Alloy team**: who from Alloy approves the JSON shape before first release? (One-time blocker.)
6. **Scraper failure policy**: if one secondary source is broken (vendor redesigned their pricing page), does the release still go out using LiteLLM-only data, or does it block? Recommend: release proceeds, broken source logged + flagged in changelog.
7. **Manual override path**: should the repo support a `manual_overrides.yaml` for entries the maintainers want to pin against scraper drift? Useful escape hatch; minor scope add.
8. **First release timing**: is there a target date relative to Alloy v1.0?

## What this is NOT

- A pricing optimisation engine
- A model catalog (capabilities are metadata, not the primary purpose)
- A live API (it's a static artefact published as releases)
- A negotiated-rates registry (those stay private to each Alloy customer)
- A model recommendation engine

Keep scope tight. Rate card in, rate card out.

## Constraints from TensorFoundry house style

- Australian English in user-facing copy (organise, behaviour, licence, colour)
- No em-dashes
- Comments explain WHY, not WHAT
- No emojis in code, commits, or docs unless explicitly requested
- Concise, direct prose

## What the Opus session is being asked to do

- Read this spec
- Discuss any of the open questions with the user before building
- Plan the implementation (Python modules, scraper interfaces, merge logic, workflow design)
- Delegate the build to a Sonnet agent (or split across multiple agents if useful)
- Land the initial repo with: working LiteLLM source, filter + merge skeleton, schema validation, test scaffolding, nightly workflow, signing wired in but possibly inactive until first real release
- Stand up the GitHub repo with appropriate visibility (public), branch protection, and CI
- Produce a v0.1 release as the bootstrap, even if not all secondary scrapers are implemented yet

Secondary scrapers can land in follow-up PRs. The bones (LiteLLM-only end-to-end pipeline with releases) is the v0.1 milestone.
