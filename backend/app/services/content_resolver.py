"""Resolve message content from inline text or remote .md URLs.

Used by both CLI (which also supports local files) and API endpoints.
"""

import niquests


def resolve_remote_content(text: str) -> str:
    """If `text` looks like a URL ending in .md, fetch and return its content.
    Otherwise return text as-is.
    """
    t = text.strip()
    if t.startswith(("http://", "https://")) and t.rsplit("?", 1)[0].endswith(".md"):
        try:
            r = niquests.get(t, timeout=30)
            r.raise_for_status()
            return r.text
        except niquests.RequestException:
            pass  # If fetch fails, use the URL as literal text (graceful degradation)
    return text
