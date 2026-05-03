from collections.abc import Iterable

from selectolax.parser import HTMLParser, Node

from rate_card.sources._scraper import (
    BaseScraper,
    ScrapedRow,
    _col_index,
    _table_headers,
    parse_price,
)
from rate_card.types import ModalityPricing, PricingTier

# OpenAI pricing tables have three shapes:
#   A: 7 columns - Model, ShortInput, ShortCachedInput, ShortOutput, LongInput, LongCachedInput, LongOutput
#   B: 5 columns - Model, Modality, Input, CachedInput, Output  (multi-modal)
#   C: 5 columns - Category, Model, Input, CachedInput, Output  (or 4 cols without cache)
#
# The page uses a content-switcher with data-value="standard" | "batch" | "flex" | "priority".
# We only read Standard tables. Batch tables contain half-price rates.


def _ancestor_data_value(node: Node) -> str | None:
    """Walk up the DOM and return the first data-value attribute found."""
    current = node.parent
    for _ in range(20):
        if current is None:
            return None
        dv = current.attributes.get("data-value")
        if dv:
            return str(dv)
        current = current.parent
    return None


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


def _extract_modality_table(table: Node) -> list[ScrapedRow]:
    """Extract rows from a table with Model, Modality, Input, Cached input, Output columns.

    Anchor on Modality column rather than row index because OpenAI may reorder rows.
    The model name only appears in the first row of each model group; continuation rows
    carry only modality and price cells. Text modality populates top-level fields; all
    other modalities populate modality_pricing.
    """
    headers = _table_headers(table)
    mi = _col_index(headers, "Model")
    mod_i = _col_index(headers, "Modality")
    ii = _col_index(headers, "Input")
    oi = _col_index(headers, "Output")
    ci = next(
        (i for i, h in enumerate(headers) if "cached input" in h.lower()),
        None,
    )
    if mi is None or mod_i is None or ii is None:
        return []

    # The number of header columns tells us how many cells a full row has.
    # Continuation rows are missing the Model cell (they have one fewer cell),
    # so they are shorter than the full header count.
    full_col_count = len(headers)

    # Group rows by model: a row is a new model when it has the full complement of cells.
    groups: list[tuple[str, list[list[str]]]] = []
    current_model: str | None = None
    current_modality_rows: list[list[str]] = []

    for tr in table.css("tbody tr"):
        cells = [td.text(strip=True) for td in tr.css("td")]
        if not cells:
            continue
        # A full row has exactly full_col_count cells and a non-empty Model column.
        if len(cells) >= full_col_count and cells[mi].strip():
            if current_model is not None:
                groups.append((current_model, current_modality_rows))
            current_model = cells[mi].strip()
            current_modality_rows = [cells]
        elif current_model is not None:
            # Continuation row: no Model cell. Modality is in cells[0], prices follow.
            current_modality_rows.append(cells)

    if current_model is not None:
        groups.append((current_model, current_modality_rows))

    results: list[ScrapedRow] = []
    for model_id, modality_rows in groups:
        text_inp: float | None = None
        text_out: float | None = None
        text_cache: float | None = None
        mp: dict[str, ModalityPricing] = {}

        for cells in modality_rows:
            # Full rows have the Model cell; continuation rows are shifted left by one.
            if len(cells) >= full_col_count:
                modality_cell = mod_i
                inp_cell = ii
                out_cell = oi
                cache_cell = ci
            else:
                # Continuation row: Modality at index 0, then prices follow the same
                # relative order as the header (Input, Cached input, Output).
                modality_cell = 0
                inp_cell = 1 if ii is not None else None
                cache_cell = 2 if ci is not None else None
                out_cell = 3 if oi is not None else (2 if ci is None else None)

            if modality_cell is None or modality_cell >= len(cells):
                continue
            modality = cells[modality_cell].strip().lower()
            inp = (
                parse_price(cells[inp_cell])
                if inp_cell is not None and inp_cell < len(cells)
                else None
            )
            out = (
                parse_price(cells[out_cell])
                if out_cell is not None and out_cell < len(cells)
                else None
            )
            cache = (
                parse_price(cells[cache_cell])
                if cache_cell is not None and cache_cell < len(cells)
                else None
            )

            if modality == "text":
                text_inp = inp
                text_out = out
                text_cache = cache
            elif modality and (inp is not None or out is not None):
                block: ModalityPricing = {}
                if inp is not None:
                    block["input_per_million"] = inp
                if out is not None:
                    block["output_per_million"] = out
                if cache is not None:
                    block["cache_read_per_million"] = cache
                if block.get("input_per_million") is not None:
                    mp[modality] = block

        if text_inp is None and not mp:
            continue

        # Text rates are the canonical default (top-level). If no text row, skip
        # top-level price fields -- the primary source supplies them via merge.
        row: ScrapedRow = {"model_id": model_id}
        if text_inp is not None:
            row["input_per_million"] = text_inp
        if text_out is not None:
            row["output_per_million"] = text_out
        if text_cache is not None:
            row["cache_read_per_million"] = text_cache
        if mp:
            row["modality_pricing"] = mp
        results.append(row)

    return results


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

            # Only process Standard pricing tables; skip Batch, Flex, Priority.
            dv = _ancestor_data_value(table)
            if dv is not None and dv != "standard":
                continue

            # Skip fine-tuning tables (contain a "Training" column) - not token pricing.
            if any("training" in h.lower() for h in headers):
                continue

            # 7-column short/long context tables: first header is empty or "Model",
            # second is "Short context".
            if len(headers) >= 2 and "short context" in headers[1].lower():
                extracted = _extract_7col_table(table)
            elif _col_index(headers, "Modality") is not None:
                # Anchor on Modality column rather than row index because OpenAI may reorder rows.
                extracted = _extract_modality_table(table)
            else:
                extracted = _extract_model_col_table(table)

            for row in extracted:
                mid = row.get("model_id", "")
                if not mid or mid in seen:
                    continue
                seen.add(mid)
                yield row
