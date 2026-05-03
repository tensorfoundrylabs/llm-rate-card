import re
from collections.abc import Iterable

from selectolax.parser import HTMLParser

from rate_card.sources._scraper import BaseScraper, ScrapedRow

# Mistral pricing page at /pricing?tab=api renders article cards.
# Each card has a read-only input with the API model ID and text that includes
# "Input (/M tokens) <price> Output (/M tokens) <price>".
# Non-digit separators (literal backslash+n or whitespace) appear between the
# label and the price value depending on how the page is serialised, so we use
# [^\d]* as the separator matcher.
_PRICE_RE = re.compile(
    r"Input \(/M tokens\)[^\d]*\$?([\d.]+)[^\d]*Output \(/M tokens\)[^\d]*\$?([\d.]+)",
    re.IGNORECASE,
)


class Mistral(BaseScraper):
    name = "mistral-direct"
    provider = "mistral"
    url = "https://mistral.ai/pricing"

    def _extract(self, raw: str) -> Iterable[ScrapedRow]:
        tree = HTMLParser(raw)
        seen: set[str] = set()

        for article in tree.css("article"):
            # The read-only input carries the API model identifier.
            inp_el = article.css_first("input")
            if not inp_el:
                continue
            raw_val = inp_el.attrs.get("value") or ""
            # outerHTML-serialised fixtures have escaped quotes around the value.
            model_id = raw_val.strip('\\"').strip('"').strip()
            if not model_id or model_id in seen:
                continue

            text = article.text(strip=True)
            m = _PRICE_RE.search(text)
            if not m:
                continue

            seen.add(model_id)
            yield ScrapedRow(
                model_id=model_id,
                input_per_million=float(m.group(1)),
                output_per_million=float(m.group(2)),
            )
