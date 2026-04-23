"""Download media URLs with size limits and mimetype detection."""

import mimetypes
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

MAX_BYTES = 25 * 1024 * 1024  # 25 MB
TIMEOUT = 30.0


@dataclass
class Media:
    url: str
    data: bytes
    mimetype: str
    filename: str
    cid: str | None = None  # set by email sender for inline images


def _guess_mimetype(url: str, content_type: str | None) -> str:
    if content_type:
        return content_type.split(";")[0].strip()
    guess, _ = mimetypes.guess_type(url)
    return guess or "application/octet-stream"


def _filename_from_url(url: str) -> str:
    path = urlparse(url).path
    name = path.rsplit("/", 1)[-1] or "file"
    return name


def download(url: str) -> Media:
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as c:
        r = c.get(url)
    r.raise_for_status()
    if len(r.content) > MAX_BYTES:
        raise ValueError(f"media {url} exceeds {MAX_BYTES} bytes")
    return Media(
        url=url,
        data=r.content,
        mimetype=_guess_mimetype(url, r.headers.get("content-type")),
        filename=_filename_from_url(url),
    )


def download_all(urls: list[str]) -> list[Media]:
    return [download(u) for u in urls]
