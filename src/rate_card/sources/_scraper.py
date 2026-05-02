from collections.abc import Iterable, Iterator
from typing import ClassVar, Literal, TypedDict

from rate_card.sources._http import fetch_text
from rate_card.sources._normalise import round_per_million
from rate_card.types import PartialEntry, PricingTier


class ScrapedRow(TypedDict, total=False):
    model_id: str
    input_per_million: float
    output_per_million: float
    cache_read_per_million: float | None
    cache_write_per_million: float | None
    reasoning_per_million: float | None
    pricing_tiers: list[PricingTier]


class BaseScraper:
    name: ClassVar[str]
    role: ClassVar[Literal["primary", "secondary"]] = "secondary"
    provider: ClassVar[str]
    url: ClassVar[str]

    def __init__(self, *, enabled: bool = True, fixture_path: str | None = None) -> None:
        self.enabled = enabled
        self._fixture_path = fixture_path

    def fetch(self) -> str:
        """Fetch raw page text, delegating to _http.fetch_text."""
        return fetch_text(self.url, fixture_path=self._fixture_path)

    def use_fixture(self, path: str) -> None:
        """Switch to reading from a local fixture file instead of the network."""
        self._fixture_path = path

    def transform(self, raw: str) -> Iterator[PartialEntry]:
        """Iterate extracted rows and convert each to a PartialEntry."""
        for row in self._extract(raw):
            yield self._row_to_entry(row)

    def _extract(self, raw: str) -> Iterable[ScrapedRow]:
        raise NotImplementedError

    def _row_to_entry(self, row: ScrapedRow) -> PartialEntry:
        model_id: str = row["model_id"]
        entry: PartialEntry = {
            "key": f"{self.provider}:{model_id}",
            "provider": self.provider,  # type: ignore[typeddict-item]
            "model_id": model_id,
            "sources": [self.name],
            "source_url": self.url,
        }

        _numeric_fields = (
            "input_per_million",
            "output_per_million",
            "cache_read_per_million",
            "cache_write_per_million",
            "reasoning_per_million",
        )
        for field in _numeric_fields:
            if field in row:
                raw_value = row[field]  # type: ignore[literal-required]
                entry[field] = round_per_million(raw_value) if raw_value is not None else None  # type: ignore[literal-required]

        if "pricing_tiers" in row:
            entry["pricing_tiers"] = row["pricing_tiers"]

        return entry
