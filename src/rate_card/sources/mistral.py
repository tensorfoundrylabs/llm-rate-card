import json
import re
from collections.abc import Iterable
from typing import Any

from selectolax.parser import HTMLParser

from rate_card.sources._scraper import BaseScraper, ScrapedRow, parse_rsc_block

# Price values in the RSC block are HTML-wrapped, e.g. "<p>$0.5</p>".
# Strip tags then parse the leading numeric value.
_PRICE_RE = re.compile(r"\$?([\d.]+)")

# The pricing data lives in a JSON structure keyed by "apis" inside the RSC block.
_APIS_RE = re.compile(r'\{"apis":\[(.+)\]\}', re.DOTALL)


def _parse_dollar(html_str: str) -> float | None:
    """Extract a price from an HTML-wrapped price string like '<p>$0.5</p>'."""
    text = HTMLParser(html_str).text(strip=True)
    m = _PRICE_RE.search(text)
    return float(m.group(1)) if m else None


class Mistral(BaseScraper):
    name = "mistral-direct"
    provider = "mistral"
    url = "https://mistral.ai/pricing"

    def _extract(self, raw: str) -> Iterable[ScrapedRow]:
        block = parse_rsc_block(raw, "api_endpoint")
        if not block:
            return

        m = _APIS_RE.search(block)
        if not m:
            return

        try:
            apis: list[Any] = json.loads("[" + m.group(1) + "]")
        except json.JSONDecodeError:
            return

        seen: set[str] = set()
        for api in apis:
            model_id: str = api.get("api_endpoint") or ""
            if not model_id or model_id in seen:
                continue

            prices: list[Any] = api.get("price") or []
            input_price: float | None = None
            output_price: float | None = None
            for price_entry in prices:
                label: str = price_entry.get("value") or ""
                dollar_html: str = price_entry.get("price_dollar") or ""
                if not dollar_html:
                    continue
                if label.startswith("Input") and "/M" in label:
                    input_price = _parse_dollar(dollar_html)
                elif label.startswith("Output") and "/M" in label:
                    output_price = _parse_dollar(dollar_html)

            if input_price is None and output_price is None:
                continue

            seen.add(model_id)
            row: ScrapedRow = {"model_id": model_id}
            if input_price is not None:
                row["input_per_million"] = input_price
            if output_price is not None:
                row["output_per_million"] = output_price
            yield row
