import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal

from rate_card.sources._http import fetch_text
from rate_card.sources._normalise import round_per_million
from rate_card.types import Capability, Mode, PartialEntry, PricingTier, Provider

logger = logging.getLogger(__name__)

_PROVIDER_MAP: dict[str, Provider] = {
    "anthropic": "anthropic",
    "openai": "openai",
    "azure": "azure",
    "azure_ai": "azure",
    "bedrock": "bedrock",
    "bedrock_converse": "bedrock",
    "vertex_ai": "vertex",
    "vertex_ai-language-models": "vertex",
    "vertex_ai_beta": "vertex",
    "vertex_ai-anthropic_models": "vertex",
    "gemini": "gemini",
    "ollama": "ollama",
    "ollama_chat": "ollama",
    "openrouter": "openrouter",
    "deepseek": "deepseek",
    "groq": "groq",
    "perplexity": "perplexity",
    "mistral": "mistral",
    "cohere": "cohere",
    "cohere_chat": "cohere",
    "huggingface": "huggingface",
    "replicate": "replicate",
    "text-completion-openai": "openai",
}

_CAPABILITY_MAP: dict[str, Capability] = {
    "supports_function_calling": "tools",
    "supports_response_schema": "structured_output",
    "supports_prompt_caching": "prompt_caching",
    "supports_reasoning": "reasoning",
    "supports_vision": "vision",
    "supports_audio_input": "audio_input",
    "supports_audio_output": "audio_output",
    "supports_pdf_input": "pdf_input",
    "supports_web_search": "web_search",
}

_VALID_MODES: frozenset[Mode] = frozenset(
    {
        "chat",
        "completion",
        "embedding",
        "image_generation",
        "audio_transcription",
        "audio_speech",
        "moderation",
        "rerank",
        "search",
    }
)

_TOKENS_PER_MILLION = 1_000_000


def _map_provider(litellm_provider: str) -> Provider | None:
    provider = _PROVIDER_MAP.get(litellm_provider)
    if provider is None:
        logger.debug("unknown litellm_provider %r, skipping entry", litellm_provider)
    return provider


def _derive_key_and_model_id(raw_key: str, provider: Provider) -> tuple[str, str]:
    model_id = raw_key
    # Strip provider prefixes so model_id matches what the provider API expects
    for prefix in ("bedrock/", "gemini/", "vertex_ai/", "openrouter/", "mistral/", "deepseek/"):
        if model_id.startswith(prefix):
            model_id = model_id[len(prefix) :]
            break
    key = f"{provider}:{model_id}"
    return key, model_id


def _build_capabilities(entry: dict[str, Any]) -> list[Capability]:
    caps: list[Capability] = []
    for field, cap in _CAPABILITY_MAP.items():
        value = entry.get(field)
        if value is True:
            caps.append(cap)
        elif value is not None and value is not False:
            logger.debug("unexpected value for %r: %r", field, value)
    for field in entry:
        if field.startswith("supports_") and field not in _CAPABILITY_MAP:
            logger.debug("unmapped supports_ field %r, ignoring", field)
    return caps


def _build_pricing_tiers(entry: dict[str, Any]) -> list[PricingTier]:
    tiers: list[PricingTier] = []
    if entry.get("input_cost_per_token_above_200k_tokens") is not None:
        tier: PricingTier = {"above_input_tokens": 200_000}
        in_cost = entry.get("input_cost_per_token_above_200k_tokens")
        if in_cost is not None:
            tier["input_per_million"] = round_per_million(float(in_cost) * _TOKENS_PER_MILLION)
        out_cost = entry.get("output_cost_per_token_above_200k_tokens")
        if out_cost is not None:
            tier["output_per_million"] = round_per_million(float(out_cost) * _TOKENS_PER_MILLION)
        cache_read = entry.get("cache_read_input_token_cost_above_200k_tokens")
        if cache_read is not None:
            tier["cache_read_per_million"] = round_per_million(
                float(cache_read) * _TOKENS_PER_MILLION
            )
        cache_write = entry.get("cache_creation_input_token_cost_above_200k_tokens")
        if cache_write is not None:
            tier["cache_write_per_million"] = round_per_million(
                float(cache_write) * _TOKENS_PER_MILLION
            )
        tiers.append(tier)
    return tiers


def _transform_entry(raw_key: str, entry: dict[str, Any]) -> PartialEntry | None:
    litellm_provider = entry.get("litellm_provider", "")
    provider = _map_provider(str(litellm_provider))
    if provider is None:
        return None

    raw_mode = entry.get("mode", "chat")
    mode: Mode = raw_mode if raw_mode in _VALID_MODES else "chat"

    # Entries without input pricing are not usable for cost calculation.
    # Output pricing is optional: image-generation models output bytes, not tokens.
    input_cost = entry.get("input_cost_per_token")
    output_cost = entry.get("output_cost_per_token")
    if input_cost is None:
        return None

    key, model_id = _derive_key_and_model_id(raw_key, provider)

    partial: PartialEntry = {
        "key": key,
        "provider": provider,
        "model_id": model_id,
        "mode": mode,
        "input_per_million": round_per_million(float(input_cost) * _TOKENS_PER_MILLION),
        "sources": ["litellm"],
    }
    if output_cost is not None:
        partial["output_per_million"] = round_per_million(float(output_cost) * _TOKENS_PER_MILLION)

    context = entry.get("max_input_tokens") or entry.get("max_tokens")
    if context is not None:
        partial["context_window"] = int(context)

    max_out = entry.get("max_output_tokens")
    if max_out is not None:
        partial["max_output_tokens"] = int(max_out)

    cache_read = entry.get("cache_read_input_token_cost")
    if cache_read is not None:
        partial["cache_read_per_million"] = round_per_million(
            float(cache_read) * _TOKENS_PER_MILLION
        )

    cache_write = entry.get("cache_creation_input_token_cost")
    if cache_write is not None:
        partial["cache_write_per_million"] = round_per_million(
            float(cache_write) * _TOKENS_PER_MILLION
        )

    reasoning_cost = entry.get("output_cost_per_reasoning_token")
    if reasoning_cost is not None:
        partial["reasoning_per_million"] = round_per_million(
            float(reasoning_cost) * _TOKENS_PER_MILLION
        )

    tiers = _build_pricing_tiers(entry)
    if tiers:
        partial["pricing_tiers"] = tiers

    partial["capabilities"] = _build_capabilities(entry)

    deprecation = entry.get("deprecation_date")
    if isinstance(deprecation, str) and deprecation:
        partial["deprecation_date"] = deprecation

    source_url = entry.get("source")
    if isinstance(source_url, str) and source_url:
        partial["source_url"] = source_url

    return partial


class LiteLLM:
    """Primary source: LiteLLM model_prices_and_context_window.json."""

    name = "litellm"
    role: Literal["primary", "secondary"] = "primary"

    def __init__(
        self,
        url: str,
        enabled: bool = True,
        fixture_path: str | None = None,
        **_kwargs: Any,
    ) -> None:
        self.url = url
        self.enabled = enabled
        self._fixture_path = fixture_path

    def fetch(self) -> dict[str, Any]:
        import json

        return json.loads(fetch_text(self.url, fixture_path=self._fixture_path))  # type: ignore[no-any-return]

    def transform(self, raw: dict[str, Any]) -> Iterable[PartialEntry]:
        for key, entry in raw.items():
            if key == "sample_spec":
                continue
            if not isinstance(entry, dict):
                continue
            result = _transform_entry(key, entry)
            if result is not None:
                yield result

    def use_fixture(self, path: str | Path) -> None:
        """Switch to reading from a local fixture file instead of the network."""
        self._fixture_path = str(path)
