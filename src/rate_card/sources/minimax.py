from collections.abc import Iterable

from rate_card.sources._scraper import (
    BaseScraper,
    ScrapedRow,
    extract_price_tables,
    make_scraped_row,
    parse_price,
)


class MiniMax(BaseScraper):
    name = "minimax-direct"
    provider = "minimax"
    url = "https://platform.minimax.io/docs/guides/pricing-paygo"

    def _extract(self, raw: str) -> Iterable[ScrapedRow]:
        for record in extract_price_tables(
            raw,
            cache_read_col="Prompt caching Read",
            cache_write_col="Prompt caching Write",
        ):
            model_id = record.get("Model", "").strip()
            if not model_id:
                continue
            row = make_scraped_row(
                model_id,
                parse_price(record.get("Input", "")),
                parse_price(record.get("Output", "")),
                cache_read=parse_price(record.get("Prompt caching Read", "")),
                cache_write=parse_price(record.get("Prompt caching Write", "")),
            )
            if row is not None:
                yield row
