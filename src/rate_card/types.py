from typing import Literal, NotRequired, TypedDict

Provider = Literal[
    "openai",
    "anthropic",
    "azure",
    "bedrock",
    "vertex",
    "gemini",
    "ollama",
    "openai_compatible",
    "openrouter",
    "deepseek",
    "groq",
    "perplexity",
    "mistral",
    "cohere",
    "huggingface",
    "replicate",
]

Mode = Literal[
    "chat",
    "completion",
    "embedding",
    "image_generation",
    "audio_transcription",
    "audio_speech",
    "moderation",
    "rerank",
    "search",
]

Capability = Literal[
    "streaming",
    "vision",
    "tools",
    "structured_output",
    "prompt_caching",
    "reasoning",
    "audio_input",
    "audio_output",
    "pdf_input",
    "web_search",
    "batch",
]


class PricingTier(TypedDict, total=False):
    above_input_tokens: int
    input_per_million: float
    output_per_million: float
    cache_read_per_million: float | None
    cache_write_per_million: float | None


class PartialEntry(TypedDict, total=False):
    """Intermediate shape produced by a source. Only key is required."""

    key: str
    provider: Provider
    model_id: str
    mode: Mode
    input_per_million: float
    output_per_million: float
    cache_read_per_million: float | None
    cache_write_per_million: float | None
    reasoning_per_million: float | None
    pricing_tiers: list[PricingTier]
    context_window: int
    max_output_tokens: int | None
    capabilities: list[Capability]
    deprecation_date: str | None
    verified: str
    sources: list[str]
    source_url: str | None


class FullEntry(TypedDict):
    """Validated entry that matches the schema model definition."""

    key: str
    provider: Provider
    model_id: str
    mode: Mode
    input_per_million: float
    output_per_million: float
    cache_read_per_million: NotRequired[float | None]
    cache_write_per_million: NotRequired[float | None]
    reasoning_per_million: NotRequired[float | None]
    pricing_tiers: NotRequired[list[PricingTier]]
    context_window: int
    max_output_tokens: NotRequired[int | None]
    capabilities: list[Capability]
    deprecation_date: NotRequired[str | None]
    verified: str
    sources: list[str]
    source_url: NotRequired[str | None]


class Attribution(TypedDict):
    name: str
    license: str
    url: str
    role: str


class Release(TypedDict, total=False):
    version: str
    generated_at: str
    source_commit: str
    signature_url: str


class Document(TypedDict):
    """Top-level rate card document."""

    schema_version: str
    name: Literal["TensorFoundry LLM Rate Card"]
    author: Literal["TensorFoundry Pty Ltd"]
    homepage: str
    license: str
    license_url: NotRequired[str]
    attribution: NotRequired[list[Attribution]]
    currency: str
    release: Release
    content_hash: str
    models: list[FullEntry]
