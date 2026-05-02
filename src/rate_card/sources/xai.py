import json
import re
from collections.abc import Iterable

from rate_card.sources._scraper import BaseScraper, ScrapedRow

# Unit is 1e-4 USD per million tokens (i.e., $n10000 = $1.00/M).
_UNIT = 1e-4

# RSC block containing model list; matched by presence of auth_mgmt.ListModelsForTeamResponse.
_RSC_MARKER = "ListModelsForTeamResponse"
_BLOCK_RE = re.compile(r'self\.__next_f\.push\(\[1,"(.+?)"\]\)', re.DOTALL)
_MODEL_RE = re.compile(
    r'"name":"(?P<name>[^"]+)"'
    r'.*?"promptTextTokenPrice":"\$n(?P<inp>\d+)"'
    r'.*?"cachedPromptTokenPrice":"(?:\$n(?P<cache>\d+)|[^"]*)"'
    r'.*?"completionTextTokenPrice":"\$n(?P<out>\d+)"',
)


def _parse_rsc_block(html: str) -> str | None:
    """Return the unescaped RSC block containing xAI model pricing."""
    for raw in _BLOCK_RE.findall(html):
        if _RSC_MARKER in raw:
            result: str = json.loads(f'"{raw}"')
            return result
    return None


class XAI(BaseScraper):
    name = "xai-direct"
    provider = "xai"
    url = "https://docs.x.ai/developers/models"

    def _extract(self, raw: str) -> Iterable[ScrapedRow]:
        block = _parse_rsc_block(raw)
        if block is None:
            return

        seen: set[str] = set()
        for m in _MODEL_RE.finditer(block):
            name = m.group("name")
            model_id = f"xai/{name}"
            if model_id in seen:
                continue
            seen.add(model_id)

            inp = int(m.group("inp")) * _UNIT
            out = int(m.group("out")) * _UNIT
            row: ScrapedRow = {
                "model_id": model_id,
                "input_per_million": inp,
                "output_per_million": out,
            }
            cache_str = m.group("cache")
            if cache_str:
                row["cache_read_per_million"] = int(cache_str) * _UNIT
            yield row
