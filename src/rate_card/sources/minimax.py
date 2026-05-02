from collections.abc import Iterable

from rate_card.sources._scraper import BaseScraper, ScrapedRow, extract_price_tables, parse_price


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
            input_price = parse_price(record.get("Input", ""))
            output_price = parse_price(record.get("Output", ""))
            if input_price is None and output_price is None:
                continue
            row: ScrapedRow = {"model_id": model_id}
            if input_price is not None:
                row["input_per_million"] = input_price
            if output_price is not None:
                row["output_per_million"] = output_price
            cache_read = parse_price(record.get("Prompt caching Read", ""))
            if cache_read is not None:
                row["cache_read_per_million"] = cache_read
            cache_write = parse_price(record.get("Prompt caching Write", ""))
            if cache_write is not None:
                row["cache_write_per_million"] = cache_write
            yield row
