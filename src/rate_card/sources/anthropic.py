import re
from collections.abc import Iterable

from selectolax.parser import HTMLParser

from rate_card.sources._scraper import BaseScraper, ScrapedRow

# Anthropic table is transposed: columns are models, rows are features.
# Anchor on heading-text row labels, not Tailwind class names, because the latter rotate.
_PRICE_RE = re.compile(
    r"\$(\d+(?:\.\d+)?)\s*/\s*input\s+MTok.*?\$(\d+(?:\.\d+)?)\s*/\s*output\s+MTok",
    re.DOTALL,
)


class Anthropic(BaseScraper):
    name = "anthropic-direct"
    provider = "anthropic"
    url = "https://docs.anthropic.com/en/docs/about-claude/models/overview"

    def _extract(self, raw: str) -> Iterable[ScrapedRow]:
        tree = HTMLParser(raw)

        for table in tree.css("table"):
            rows = table.css("tbody tr")
            if not rows:
                continue

            # The header row in thead gives model column names.
            header_cells = table.css("thead th")
            if len(header_cells) < 2:
                continue

            # Find the API alias row and pricing row by first-cell label.
            alias_cells: list[str] = []
            pricing_cells: list[str] = []

            for tr in rows:
                cells = [td.text(strip=True) for td in tr.css("td")]
                if not cells:
                    continue
                label = cells[0].lower()
                if "api alias" in label or (label.startswith("claude api") and "alias" in label):
                    alias_cells = cells[1:]
                elif label.startswith("pricing"):
                    pricing_cells = cells[1:]

            if not alias_cells or not pricing_cells:
                continue

            n_models = min(len(alias_cells), len(pricing_cells))
            for i in range(n_models):
                model_id = alias_cells[i].strip()
                if not model_id:
                    continue
                m = _PRICE_RE.search(pricing_cells[i])
                if not m:
                    continue
                inp = float(m.group(1))
                out = float(m.group(2))
                row: ScrapedRow = {
                    "model_id": model_id,
                    "input_per_million": inp,
                    "output_per_million": out,
                }
                yield row
