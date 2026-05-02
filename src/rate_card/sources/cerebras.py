import json
import re
from collections.abc import Iterable

from rate_card.sources._scraper import BaseScraper, ScrapedRow

# Cerebras pricing page has no HTML tables; data lives in RSC push blocks.
# Extraction uses regex over the unescaped RSC payload rather than HTML parsing.
_BLOCK_RE = re.compile(r"self\.__next_f\.push\(\[1,\"(.+?)\"\]\)", re.DOTALL)
# Row format: "cells":["[PROVIDER]Name","~N tokens/s","$$X.XX/M tokens","$$Y.YY/M tokens"]
_ROW_RE = re.compile(
    r'"cells":\["(?:\[[^\]]+\])?([^"]+)","[^"]+","\$\$([^/]+)/M[^"]*","\$\$([^/]+)/M[^"]*"\]'
)
_PRICE_RE = re.compile(r"([\d.]+)")

# Map page display names to LiteLLM model IDs; Cerebras uses non-standard slugs.
_NAME_MAP: dict[str, str] = {
    "ZAI GLM 4.7": "cerebras/zai-glm-4.7",
    "GPT OSS 120B": "cerebras/gpt-oss-120b",
    "Llama 3.1 8B": "cerebras/llama3.1-8b",
    "Llama 3.3 70B": "cerebras/llama-3.3-70b",
    "Qwen 3 235B Instruct": "cerebras/qwen-3-235b",
    "Qwen 3 32B": "cerebras/qwen-3-32b",
}


def _slug(name: str) -> str:
    """Produce a fallback slug for unmapped model names."""
    name = re.sub(r"\s+", "-", name.strip().lower())
    name = re.sub(r"[^a-z0-9./\-]", "", name)
    name = re.sub(r"-+", "-", name)
    return f"cerebras/{name.strip('-')}"


def _parse_blocks(html: str) -> str | None:
    """Return the unescaped RSC block that contains pricing cell arrays."""
    for raw in _BLOCK_RE.findall(html):
        if "cells" in raw and "/M tokens" in raw:
            result: str = json.loads(f'"{raw}"')
            return result
    return None


class Cerebras(BaseScraper):
    name = "cerebras-direct"
    provider = "cerebras"
    url = "https://www.cerebras.ai/pricing"

    def _extract(self, raw: str) -> Iterable[ScrapedRow]:
        block = _parse_blocks(raw)
        if block is None:
            return

        for m in _ROW_RE.finditer(block):
            display_name = m.group(1).strip().rstrip("*").strip()
            inp_str = m.group(2).strip()
            out_str = m.group(3).strip()

            # Skip header row
            if display_name.lower() == "model":
                continue

            inp_m = _PRICE_RE.search(inp_str)
            out_m = _PRICE_RE.search(out_str)
            if not inp_m or not out_m:
                continue

            model_id = _NAME_MAP.get(display_name, _slug(display_name))
            yield ScrapedRow(
                model_id=model_id,
                input_per_million=float(inp_m.group(1)),
                output_per_million=float(out_m.group(1)),
            )
