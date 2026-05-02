from pathlib import Path

import httpx


def fetch_text(
    url: str,
    *,
    fixture_path: str | Path | None = None,
    timeout: float = 30.0,
    headers: dict[str, str] | None = None,
) -> str:
    """Fetch text from url, or read from fixture_path if provided."""
    if fixture_path is not None:
        return Path(fixture_path).read_text(encoding="utf-8")
    response = httpx.get(url, timeout=timeout, headers=headers or {}, follow_redirects=True)
    response.raise_for_status()
    return response.text
