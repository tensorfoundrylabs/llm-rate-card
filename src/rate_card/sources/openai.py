from collections.abc import Iterable

from selectolax.parser import HTMLParser, Node

from rate_card.sources._scraper import (
    BaseScraper,
    ScrapedRow,
    _col_index,
    _table_headers,
    parse_price,
)
from rate_card.types import PricingTier

# OpenAI pricing tables have two shapes:
#   A: 7 columns - Model, ShortInput, ShortCachedInput, ShortOutput, LongInput, LongCachedInput, LongOutput
#   B: 5 columns - Category, Model, Input, CachedInput, Output  (or 4 cols without cache)


def _extract_7col_table(table: Node) -> list[ScrapedRow]:
    """Extract rows from a Short/Long context split table (7 data columns)."""
    rows: list[ScrapedRow] = []
    for tr in table.css("tbody tr"):
        cells = [td.text(strip=True) for td in tr.css("td")]
        if len(cells) < 4:
            continue
        model_id = cells[0].strip()
        if not model_id:
            continue
        inp = parse_price(cells[1])
        cache = parse_price(cells[2]) if len(cells) > 2 else None
        out = parse_price(cells[3]) if len(cells) > 3 else None
        if inp is None and out is None:
            continue
        row: ScrapedRow = {"model_id": model_id}
        if inp is not None:
            row["input_per_million"] = inp
        if out is not None:
            row["output_per_million"] = out
        if cache is not None:
            row["cache_read_per_million"] = cache
        # Long context tier (columns 4-6)
        if len(cells) >= 7:
            long_inp = parse_price(cells[4])
            long_out = parse_price(cells[6])
            if long_inp is not None or long_out is not None:
                tier: PricingTier = {"above_input_tokens": 200_000}
                if long_inp is not None:
                    tier["input_per_million"] = long_inp
                if long_out is not None:
                    tier["output_per_million"] = long_out
                long_cache = parse_price(cells[5]) if len(cells) > 5 else None
                if long_cache is not None:
                    tier["cache_read_per_million"] = long_cache
                row["pricing_tiers"] = [tier]
        rows.append(row)
    return rows


def _extract_model_col_table(table: Node) -> list[ScrapedRow]:
    """Extract rows from a table with a Model column plus Input/Output columns."""
    headers = _table_headers(table)
    if not headers:
        return []
    mi = _col_index(headers, "Model")
    ii = _col_index(headers, "Input")
    oi = _col_index(headers, "Output")
    if mi is None or (ii is None and oi is None):
        return []
    # Cached input index - must not match "Cached output"
    ci = next(
        (i for i, h in enumerate(headers) if "cached input" in h.lower()),
        None,
    )

    rows: list[ScrapedRow] = []
    for tr in table.css("tbody tr"):
        cells = [td.text(strip=True) for td in tr.css("td")]
        required = [x for x in [mi, ii, oi] if x is not None]
        if not required or len(cells) <= max(required):
            continue
        model_id = cells[mi].strip()
        if not model_id:
            continue
        inp = parse_price(cells[ii]) if ii is not None and ii < len(cells) else None
        out = parse_price(cells[oi]) if oi is not None and oi < len(cells) else None
        if inp is None and out is None:
            continue
        row: ScrapedRow = {"model_id": model_id}
        if inp is not None:
            row["input_per_million"] = inp
        if out is not None:
            row["output_per_million"] = out
        if ci is not None and ci < len(cells):
            cache = parse_price(cells[ci])
            if cache is not None:
                row["cache_read_per_million"] = cache
        rows.append(row)
    return rows


class OpenAI(BaseScraper):
    name = "openai-direct"
    provider = "openai"
    url = "https://developers.openai.com/api/docs/pricing"

    def _extract(self, raw: str) -> Iterable[ScrapedRow]:
        tree = HTMLParser(raw)
        seen: set[str] = set()

        for table in tree.css("table"):
            headers = _table_headers(table)
            if not headers:
                continue

            # Skip fine-tuning tables (contain a "Training" column) - not token pricing.
            if any("training" in h.lower() for h in headers):
                continue

            # 7-column short/long context tables: first header is empty or "Model",
            # second is "Short context".
            if len(headers) >= 2 and "short context" in headers[1].lower():
                extracted = _extract_7col_table(table)
            else:
                extracted = _extract_model_col_table(table)

            for row in extracted:
                mid = row.get("model_id", "")
                if not mid or mid in seen:
                    continue
                seen.add(mid)
                yield row
