"""Markdown converters.

- `md_to_html`: full CommonMark → HTML for email bodies.
- `md_to_whatsapp`: best-effort conversion of common markdown syntax to
  WhatsApp's own lightweight formatting (*bold*, _italic_, ~strike~, ```code```).
  Since WhatsApp's syntax overlaps with markdown, most inputs pass through
  unchanged. We mainly strip things WA doesn't render (headers, links,
  images, HTML tags).
- `md_to_plain`: strip all formatting — used for SMS and TTS.
"""

from __future__ import annotations

import re

from markdown_it import MarkdownIt

_md = (
    MarkdownIt("commonmark", {"breaks": True, "linkify": True})
    .enable("strikethrough")
    .enable("linkify")
)


def md_to_html(text: str) -> str:
    return _md.render(text or "")


# ---- WhatsApp ----

_HEADER_RE = re.compile(r"^\s{0,3}#{1,6}\s+", re.MULTILINE)
_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD_STAR_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_BOLD_UND_RE = re.compile(r"__(.+?)__", re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_HR_RE = re.compile(r"^\s*(?:-\s*){3,}$|^\s*(?:\*\s*){3,}$|^\s*(?:_\s*){3,}$", re.MULTILINE)


def md_to_whatsapp(text: str) -> str:
    if not text:
        return ""
    s = text
    # Drop raw HTML
    s = _HTML_TAG_RE.sub("", s)
    # Drop horizontal rules
    s = _HR_RE.sub("", s)
    # Strip heading markers, keep the text
    s = _HEADER_RE.sub("", s)
    # Images → just the alt text (if any) + URL
    s = _IMG_RE.sub(lambda m: f"{m.group(1)} {m.group(2)}".strip(), s)
    # Links → "text (url)"
    s = _LINK_RE.sub(lambda m: f"{m.group(1)} ({m.group(2)})", s)
    # Bold: **x** / __x__ → *x*  (WA uses single-star bold)
    s = _BOLD_STAR_RE.sub(r"*\1*", s)
    s = _BOLD_UND_RE.sub(r"*\1*", s)
    # Collapse 3+ blank lines
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


# ---- Plain text ----

_MD_FENCE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_MD_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_MD_EMPH_RE = re.compile(r"([*_~]{1,3})(\S.*?\S|\S)\1")


def md_to_plain(text: str) -> str:
    if not text:
        return ""
    s = text
    s = _HTML_TAG_RE.sub("", s)
    s = _MD_FENCE_RE.sub(
        lambda m: m.group(0).strip("`").strip("\n"), s
    )
    s = _MD_INLINE_CODE_RE.sub(r"\1", s)
    s = _HEADER_RE.sub("", s)
    s = _IMG_RE.sub(lambda m: (m.group(1) or "").strip(), s)
    s = _LINK_RE.sub(lambda m: f"{m.group(1)} ({m.group(2)})", s)
    s = _MD_EMPH_RE.sub(r"\2", s)
    s = _HR_RE.sub("", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()
