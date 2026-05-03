import json
import re
from collections.abc import Iterable, Iterator
from typing import ClassVar, Literal, TypedDict

from selectolax.parser import HTMLParser, Node

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


def parse_price(text: str) -> float | None:
    """Parse a price cell like '$1.40' or '0.30' into a float; return None for free/empty/dashes."""
    s = text.strip()
    if not s or s.lower() in ("free", "-", "\\", "n/a", "tbd"):
        return None
    m = re.match(r"^\$?([\d,]+\.?\d*)", s)
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def _col_index(headers: list[str], *candidates: str) -> int | None:
    """Return the index of the first header matching any candidate (case-insensitive substring)."""
    lower = [h.lower() for h in headers]
    for cand in candidates:
        cand_l = cand.lower()
        for i, h in enumerate(lower):
            if cand_l in h:
                return i
    return None


def _table_headers(table: Node) -> list[str]:
    """Return header cell texts from thead > th, falling back to first tr > th."""
    ths = table.css("thead th")
    if not ths:
        ths = table.css("tr:first-child th")
    return [th.text(strip=True) for th in ths]


def extract_price_tables(
    html: str,
    *,
    model_col: str = "Model",
    input_col: str = "Input",
    output_col: str = "Output",
    cache_read_col: str | None = "Cached Input",
    cache_write_col: str | None = None,
) -> list[dict[str, str]]:
    """Extract rows from every HTML table whose headers contain model/input/output columns.

    Returns a list of dicts keyed by the column header labels passed in.
    Tables without a model column and at least one price column are skipped.
    """
    tree = HTMLParser(html)
    rows: list[dict[str, str]] = []

    for table in tree.css("table"):
        headers = _table_headers(table)
        if not headers:
            continue
        mi = _col_index(headers, model_col)
        ii = _col_index(headers, input_col)
        oi = _col_index(headers, output_col)
        if mi is None or (ii is None and oi is None):
            continue
        cr_i = _col_index(headers, cache_read_col) if cache_read_col else None
        cw_i = _col_index(headers, cache_write_col) if cache_write_col else None

        for tr in table.css("tbody tr"):
            cells = [td.text(strip=True) for td in tr.css("td")]
            required = [x for x in [mi, ii, oi] if x is not None]
            if not required or len(cells) <= max(required):
                continue
            record: dict[str, str] = {}
            record[model_col] = cells[mi] if mi < len(cells) else ""
            if ii is not None and ii < len(cells):
                record[input_col] = cells[ii]
            if oi is not None and oi < len(cells):
                record[output_col] = cells[oi]
            if cr_i is not None and cr_i < len(cells):
                record[cache_read_col] = cells[cr_i]  # type: ignore[index]
            if cw_i is not None and cw_i < len(cells):
                record[cache_write_col] = cells[cw_i]  # type: ignore[index]
            rows.append(record)
    return rows


_RSC_BLOCK_RE = re.compile(r'self\.__next_f\.push\(\[1,"(.+?)"\]\)', re.DOTALL)


def parse_rsc_block(html: str, marker: str) -> str | None:
    """Return the first unescaped RSC push block whose raw content contains *marker*.

    Next.js RSC payloads are embedded as ``self.__next_f.push([1, "<escaped>"])``
    fragments. This helper finds the block matching *marker*, JSON-unescapes it,
    and returns the plain text for further parsing.
    """
    for raw in _RSC_BLOCK_RE.findall(html):
        if marker in raw:
            result: str = json.loads(f'"{raw}"')
            return result
    return None


def make_scraped_row(
    model_id: str,
    input_price: float | None,
    output_price: float | None,
    *,
    cache_read: float | None = None,
    cache_write: float | None = None,
    reasoning: float | None = None,
) -> ScrapedRow | None:
    """Build a :class:`ScrapedRow` from optional price values.

    Returns ``None`` when both *input_price* and *output_price* are ``None``,
    so callers can skip that row without repeating the guard.
    """
    if input_price is None and output_price is None:
        return None
    row: ScrapedRow = {"model_id": model_id}
    if input_price is not None:
        row["input_per_million"] = input_price
    if output_price is not None:
        row["output_per_million"] = output_price
    if cache_read is not None:
        row["cache_read_per_million"] = cache_read
    if cache_write is not None:
        row["cache_write_per_million"] = cache_write
    if reasoning is not None:
        row["reasoning_per_million"] = reasoning
    return row


class BaseScraper:
    name: ClassVar[str]
    role: ClassVar[Literal["primary", "secondary"]] = "secondary"
    provider: ClassVar[str]
    url: ClassVar[str]

    def __init__(
        self,
        *,
        enabled: bool = True,
        fixture_path: str | None = None,
        **_kwargs: object,
    ) -> None:
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
