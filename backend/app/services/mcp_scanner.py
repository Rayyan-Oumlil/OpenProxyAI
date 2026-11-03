"""Scan MCP tool descriptions and tool results for prompt injection (design-specs A.4).

Both are text an upstream server controls and an agent reads as trusted context, so they are the
main carrier for tool poisoning and indirect prompt injection. The scanner is pure, deterministic and
cheap (no model call in the request path); it looks for the carriers attackers actually use:

    unicode_tag          invisible Unicode tag characters (U+E0000-E007F) that smuggle ASCII
    invisible_char       zero-width / bidi control characters (or long runs of ZWJ/ZWNJ)
    instruction_override "ignore previous instructions", "disregard your rules", ...
    hidden_instruction_tag  <IMPORTANT>, <system>, <instructions> pseudo-markup
    concealment          "do not tell the user", "without informing the user"
    markdown_exfil       markdown images whose URL carries a query string (rendered = data leaves)
    base64_blob          long base64 runs hiding a payload
    oversized            text larger than MAX_TEXT_CHARS, or nested deeper than MAX_DEPTH

Per-server ``scan_mode``: off | log (report only) | redact (sanitise and serve) | block.
Heuristics produce false positives (a CDN image with a long query string, say), which is why the
default is ``log``. Findings are category names only; the offending text is never copied elsewhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

SCAN_OFF, SCAN_LOG, SCAN_REDACT, SCAN_BLOCK = "off", "log", "redact", "block"
SCAN_MODES = (SCAN_OFF, SCAN_LOG, SCAN_REDACT, SCAN_BLOCK)

MAX_TEXT_CHARS = 500_000
MAX_DEPTH = 20
MAX_NODES = 50_000
_BINARY_KEYS = frozenset({"data", "blob"})  # base64 payloads of image/audio/resource content

_TAGS = re.compile(r"[\U000e0000-\U000e007f]")
_INVISIBLE = re.compile(r"[​‎‏‪-‮⁠-⁤⁦-⁩﻿]|[​-‍⁠﻿]{3,}")

# (category, pattern). Replaced by a marker when redacting.
_PHRASES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("instruction_override", re.compile(
        r"\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+|the\s+|your\s+)*(?:previous|prior|above|earlier|preceding)\s+"
        r"(?:instructions?|prompts?|rules|guidelines|directions)\b"
        r"|\bdisregard\s+your\s+(?:training|guidelines|rules|instructions)\b"
        r"|\bnew\s+instructions\s*:",
        re.IGNORECASE)),
    ("hidden_instruction_tag", re.compile(r"</?\s*(?:important|system|instructions?|assistant|admin)\s*>", re.IGNORECASE)),
    ("concealment", re.compile(
        r"\b(?:do\s+not|don'?t|never)\s+(?:tell|mention|reveal|inform|show)\s+(?:this\s+|that\s+|it\s+)?(?:to\s+)?the\s+user\b"
        r"|\bwithout\s+(?:telling|informing|notifying|alerting)\s+the\s+user\b",
        re.IGNORECASE)),
    ("markdown_exfil", re.compile(r"!\[[^\]]*\]\(\s*https?://[^)\s]*\?[^)\s]{8,}\s*\)", re.IGNORECASE)),
    ("base64_blob", re.compile(r"[A-Za-z0-9+/]{200,}={0,2}")),
)


@dataclass(frozen=True)
class ScanResult:
    categories: tuple[str, ...]  # sorted, unique; empty when clean
    value: Any  # the sanitised copy when redact=True, else the input unchanged

    @property
    def flagged(self) -> bool:
        return bool(self.categories)


def scan_text(text: str) -> set[str]:
    """Categories of injection carriers found in ``text``."""
    found: set[str] = set()
    if len(text) > MAX_TEXT_CHARS:
        found.add("oversized")
        text = text[:MAX_TEXT_CHARS]
    if _TAGS.search(text):
        found.add("unicode_tag")
    if _INVISIBLE.search(text):
        found.add("invisible_char")
    for category, pattern in _PHRASES:
        if pattern.search(text):
            found.add(category)
    return found


def redact_text(text: str) -> str:
    """Remove invisible characters, replace flagged phrases with a marker, truncate oversized text."""
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + " [truncated]"
    text = _TAGS.sub("", text)
    text = _INVISIBLE.sub("", text)
    for category, pattern in _PHRASES:
        text = pattern.sub(f"[redacted:{category}]", text)
    return text


def scan_value(value: Any, *, redact: bool = False) -> ScanResult:
    """Walk a JSON-like value (tool definition or tool result) and scan every string in it.

    Dict keys are not scanned and never rewritten, so tool names and schema property names stay stable.
    Binary payloads (``data``/``blob`` next to a ``mimeType``) are skipped.
    """
    found: set[str] = set()
    budget = [MAX_NODES]

    def walk(node: Any, depth: int) -> Any:
        budget[0] -= 1
        if budget[0] < 0 or depth > MAX_DEPTH:
            found.add("oversized")
            return node if not redact else None
        if isinstance(node, str):
            found.update(scan_text(node))
            return redact_text(node) if redact else node
        if isinstance(node, list):
            return [walk(item, depth + 1) for item in node]
        if isinstance(node, dict):
            binary = "mimeType" in node
            return {
                key: item if (binary and key in _BINARY_KEYS) else walk(item, depth + 1)
                for key, item in node.items()
            }
        return node

    scanned = walk(value, 0)
    return ScanResult(categories=tuple(sorted(found)), value=scanned if redact else value)
