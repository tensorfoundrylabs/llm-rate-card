import re
from collections.abc import Iterable, Iterator

from selectolax.parser import HTMLParser

from rate_card.sources._scraper import BaseScraper, ScrapedRow, _col_index, parse_price
from rate_card.types import PricingTier

# Alibaba Cloud DashScope tables all carry class="qwen".
# Tables have varying column counts; locate price columns by header text.
_MODEL_SLUG_RE = re.compile(r"^(qwen[\w.\-]*?)(?=[A-Z]|Batch|Context|\$)", re.ASCII)

# Matches "0<Token<=32K", "32K<Token<=128K", "256K<Token<=1M", etc.
_TIER_CTX_RE = re.compile(r"([\d.]+)(K|M)?<Token", re.IGNORECASE)

# Row cells[0] values that indicate a row type we should skip.
_SKIP_LABELS = frozenset(
    {
        "Input: Text",
        "Non-thinking mode",
        "Text",
        "Text/Image",
        "Text/Image/Video",
        "Model",
    }
)


def _clean_model(raw: str) -> str:
    """Strip marketing suffixes (e.g. 'Batch calling50% off') from a model name cell."""
    m = _MODEL_SLUG_RE.match(raw)
    if m:
        return m.group(1).rstrip("-").rstrip(".")
    return raw


def _tier_lower_bound(ctx: str) -> int | None:
    """Return the lower-bound token count from a context-range string, or None."""
    m = _TIER_CTX_RE.match(ctx.strip())
    if not m:
        return None
    val = float(m.group(1))
    suffix = (m.group(2) or "").upper()
    if suffix == "M":
        val *= 1_000_000
    else:
        val *= 1_000
    return int(val)


class Qwen(BaseScraper):
    name = "qwen-direct"
    provider = "qwen"
    url = "https://www.alibabacloud.com/help/en/model-studio/model-pricing"

    def _extract(self, raw: str) -> Iterable[ScrapedRow]:
        tree = HTMLParser(raw)
        seen: set[str] = set()

        for table in tree.css("table.qwen"):
            rows = table.css("tr")
            if not rows:
                continue

            # Row 0 is always the header row.
            header_cells = [td.text(strip=True) for td in rows[0].css("td,th")]
            if not header_cells:
                continue

            # Locate price columns by header text; handle "CoT + response" suffix on output col.
            inp_i = _col_index(header_cells, "Input price")
            out_i = _col_index(header_cells, "Output price")
            if inp_i is None or out_i is None:
                continue

            # Tier continuation rows carry (ctx_range, input_price, output_price) in 3 cells.
            # These rows have no header, so we treat cells[0] as ctx and use fixed offsets.
            tier_inp_i = 1
            tier_out_i = 2

            current_model: str | None = None
            tiers: list[PricingTier] = []
            base_inp: float | None = None
            base_out: float | None = None

            def _flush() -> Iterator[ScrapedRow]:
                nonlocal current_model, tiers, base_inp, base_out
                if current_model and current_model not in seen:
                    seen.add(current_model)
                    entry: ScrapedRow = {"model_id": f"qwen/{current_model}"}
                    if base_inp is not None:
                        entry["input_per_million"] = base_inp
                    if base_out is not None:
                        entry["output_per_million"] = base_out
                    if tiers:
                        entry["pricing_tiers"] = list(tiers)
                    if base_inp is not None or base_out is not None:
                        yield entry
                current_model = None
                tiers = []
                base_inp = None
                base_out = None

            for r in rows[1:]:
                cells = [td.text(strip=True) for td in r.css("td,th")]
                if not cells:
                    continue

                c0 = cells[0]

                if c0 in _SKIP_LABELS:
                    continue

                if c0.startswith("qwen"):
                    yield from _flush()

                    current_model = _clean_model(c0)
                    base_inp = parse_price(cells[inp_i]) if inp_i < len(cells) else None
                    base_out = parse_price(cells[out_i]) if out_i < len(cells) else None

                elif c0 and "<Token" in c0 and current_model:
                    # Tier continuation row: [ctx_range, input_price, output_price]
                    lower = _tier_lower_bound(c0)
                    if lower is not None and lower > 0:
                        tier_inp = (
                            parse_price(cells[tier_inp_i]) if len(cells) > tier_inp_i else None
                        )
                        tier_out = (
                            parse_price(cells[tier_out_i]) if len(cells) > tier_out_i else None
                        )
                        tier: PricingTier = {"above_input_tokens": lower}
                        if tier_inp is not None:
                            tier["input_per_million"] = tier_inp
                        if tier_out is not None:
                            tier["output_per_million"] = tier_out
                        tiers.append(tier)

            yield from _flush()
