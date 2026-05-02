from pathlib import Path

import httpx
import pytest
from pytest_httpx import HTTPXMock

from rate_card.sources._http import fetch_text


def test_fixture_path_returns_file_content(tmp_path: Path) -> None:
    fixture = tmp_path / "data.txt"
    fixture.write_text("hello fixture", encoding="utf-8")
    result = fetch_text("https://example.com/ignored", fixture_path=fixture)
    assert result == "hello fixture"


def test_fixture_path_no_http_request(tmp_path: Path, httpx_mock: HTTPXMock) -> None:
    fixture = tmp_path / "data.txt"
    fixture.write_text("content", encoding="utf-8")
    fetch_text("https://example.com/not-called", fixture_path=fixture)
    # no registered mock means any real call would raise
    assert httpx_mock.get_requests() == []


def test_url_branch_issues_get(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(text="remote content")
    result = fetch_text("https://example.com/data")
    assert result == "remote content"
    requests = httpx_mock.get_requests()
    assert len(requests) == 1
    assert requests[0].method == "GET"


def test_url_branch_passes_headers(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(text="ok")
    fetch_text("https://example.com/data", headers={"X-Custom": "value"})
    request = httpx_mock.get_requests()[0]
    assert request.headers["x-custom"] == "value"


def test_url_branch_raises_on_non_2xx(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(status_code=404)
    with pytest.raises(httpx.HTTPStatusError):
        fetch_text("https://example.com/missing")


def test_url_branch_raises_on_500(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(status_code=500)
    with pytest.raises(httpx.HTTPStatusError):
        fetch_text("https://example.com/error")


def test_fixture_path_accepts_string(tmp_path: Path) -> None:
    fixture = tmp_path / "data.txt"
    fixture.write_text("string path content", encoding="utf-8")
    result = fetch_text("https://example.com/ignored", fixture_path=str(fixture))
    assert result == "string path content"
