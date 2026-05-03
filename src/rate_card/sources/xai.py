import re
from collections.abc import Iterable

from rate_card.sources._scraper import BaseScraper, ScrapedRow, parse_rsc_block

# Unit is 1e-4 USD per million tokens (i.e., $n10000 = $1.00/M).
_UNIT = 1e-4

# RSC block containing model list; matched by presence of auth_mgmt.ListModelsForTeamResponse.
_RSC_MARKER = "ListModelsForTeamResponse"
_MODEL_RE = re.compile(
    r'"name":"(?P<name>[^"]+)"'
    r'.*?"promptTextTokenPrice":"\$n(?P<inp>\d+)"'
    r'.*?"cachedPromptTokenPrice":"(?:\$n(?P<cache>\d+)|[^"]*)"'
    r'.*?"completionTextTokenPrice":"\$n(?P<out>\d+)"',
)


class XAI(BaseScraper):
    name = "xai-direct"
    provider = "xai"
    url = "https://docs.x.ai/developers/models"

    def _extract(self, raw: str) -> Iterable[ScrapedRow]:
        block = parse_rsc_block(raw, _RSC_MARKER)
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
