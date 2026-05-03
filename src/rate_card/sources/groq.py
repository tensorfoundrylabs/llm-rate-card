import re
from collections.abc import Iterable

from selectolax.parser import HTMLParser, Node

from rate_card.sources._scraper import (
    BaseScraper,
    ScrapedRow,
    _col_index,
    _table_headers,
    parse_price,
)

# Groq table cells use a labelled-content div pattern; inner div carries the value.
_INNER_SEL = 'div[class*="contents-inner"]'


def _cell_texts(row: Node) -> list[str]:
    """Extract cell values from a Groq table row, preferring inner-content divs."""
    inner = row.css(_INNER_SEL)
    if inner:
        return [d.text(strip=True) for d in inner]
    return [td.text(strip=True) for td in row.css("td")]


def _name_to_slug(name: str) -> str:
    """Convert a human-readable Groq model name to an API slug, e.g. 'Llama 3.3 70B Versatile 128k'."""
    name = re.sub(r"\s+\d+[kK]\s*$", "", name)
    name = name.lower()
    # Preserve dots (version numbers like 3.3) and slashes; replace everything else with hyphens.
    name = re.sub(r"[^a-z0-9./]", "-", name)
    name = re.sub(r"-+", "-", name)
    return name.strip("-")


class Groq(BaseScraper):
    name = "groq-direct"
    provider = "groq"
    url = "https://groq.com/pricing"

    def _extract(self, raw: str) -> Iterable[ScrapedRow]:
        tree = HTMLParser(raw)
        seen: set[str] = set()

        for table in tree.css("table"):
            headers = _table_headers(table)
            if not headers:
                continue

            mi = _col_index(headers, "Model", "AI Model")
            ii = _col_index(headers, "Input Token", "Uncached Input")
            oi = _col_index(headers, "Output Token", "Output Tokens")
            if mi is None or (ii is None and oi is None):
                continue

            # "Cached Input" is a substring of "Uncached Input"; use a stricter prefix match.
            cr_i = next(
                (i for i, h in enumerate(headers) if h.lower().startswith("cached")),
                None,
            )

            for tr in table.css("tbody tr"):
                cells = _cell_texts(tr)
                required = [x for x in [mi, ii, oi] if x is not None]
                if not required or len(cells) <= max(required):
                    continue

                raw_id = cells[mi].strip()
                if not raw_id:
                    continue

                # Table 4 IDs already contain slashes (namespaced); table 0 names need slugification.
                model_id = f"groq/{raw_id}" if "/" in raw_id else f"groq/{_name_to_slug(raw_id)}"

                if model_id in seen:
                    continue
                seen.add(model_id)

                input_price = parse_price(cells[ii]) if ii is not None and ii < len(cells) else None
                output_price = (
                    parse_price(cells[oi]) if oi is not None and oi < len(cells) else None
                )
                if input_price is None and output_price is None:
                    continue

                row: ScrapedRow = {"model_id": model_id}
                if input_price is not None:
                    row["input_per_million"] = input_price
                if output_price is not None:
                    row["output_per_million"] = output_price
                if cr_i is not None and cr_i < len(cells):
                    cr = parse_price(cells[cr_i])
                    if cr is not None:
                        row["cache_read_per_million"] = cr
                yield row
