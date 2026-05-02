from collections.abc import Iterable

from rate_card.sources._scraper import BaseScraper, ScrapedRow, extract_price_tables, parse_price


class GLM(BaseScraper):
    name = "glm-direct"
    provider = "glm"
    url = "https://docs.z.ai/guides/overview/pricing"

    def _extract(self, raw: str) -> Iterable[ScrapedRow]:
        for record in extract_price_tables(raw, cache_read_col="Cached Input"):
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
            cache_read = parse_price(record.get("Cached Input", ""))
            if cache_read is not None:
                row["cache_read_per_million"] = cache_read
            yield row
