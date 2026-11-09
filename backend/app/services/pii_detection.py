"""The built-in PII detector: one implementation behind policy blocking, response redaction and data classification.

It finds email addresses, US Social Security numbers and payment card numbers. Presidio, when installed, replaces it
(and can find many more kinds); this is what runs by default.

Text is normalized before it is read (compatibility forms folded, so fullwidth digits and ``＠`` count; invisible
format characters removed, so a zero-width space cannot split a number). Cards must pass the Luhn check and SSNs must
be a number the Social Security Administration could issue, which keeps order numbers and version strings from being
called PII. Deliberately not detected: nine bare digits (too ambiguous), spelled-out addresses (``jane [at] example``)
and phone numbers.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Final

REDACTION: Final = "[REDACTED]"

# Order matters: it is the order entities are reported and the order a blocked request names the first one.
ENTITY_ORDER: Final = ("email", "ssn", "payment_card")

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_SSN = re.compile(r"(?<!\d)(\d{3})([-. ])(\d{2})\2(\d{4})(?!\d)")  # one separator, used consistently
_DIGIT_RUN = re.compile(r"(?<!\d)\d(?:[ -]?\d)*(?!\d)")
_CARD_LENGTHS = range(13, 20)


@dataclass(frozen=True)
class Hit:
	entity: str
	start: int
	end: int


def normalize(text: str) -> str:
	"""Fold compatibility forms (NFKC) and drop invisible format characters (zero-width, soft hyphen, bidi marks)."""
	folded = unicodedata.normalize("NFKC", text)
	return "".join(ch for ch in folded if unicodedata.category(ch) != "Cf")


def luhn_valid(digits: str) -> bool:
	if not digits or not digits.isdigit():
		return False
	total = 0
	for index, ch in enumerate(reversed(digits)):
		value = int(ch)
		if index % 2 == 1:
			value *= 2
			if value > 9:
				value -= 9
		total += value
	return total % 10 == 0


def _ssn_issuable(area: str, group: str, serial: str) -> bool:
	return "001" <= area <= "899" and area != "666" and group != "00" and serial != "0000"


def _card_hits(text: str) -> list[Hit]:
	"""Luhn-valid 13-19 digit numbers, written as whole groups (never a window that cuts a group in half)."""
	hits: list[Hit] = []
	for run in _DIGIT_RUN.finditer(text):
		groups = [(m.group(), run.start() + m.start(), run.start() + m.end()) for m in re.finditer(r"\d+", run.group())]
		i = 0
		while i < len(groups):
			found = None
			digits = ""
			for j in range(i, len(groups)):
				digits += groups[j][0]
				if len(digits) > 19:
					break
				if len(digits) in _CARD_LENGTHS and luhn_valid(digits):
					found = j
			if found is None:
				i += 1
				continue
			hits.append(Hit("payment_card", groups[i][1], groups[found][2]))
			i = found + 1
	return hits


def find(text: str) -> list[Hit]:
	"""Hits in ``text``, which must already be normalized, in the order they appear."""
	hits = [Hit("email", m.start(), m.end()) for m in _EMAIL.finditer(text)]
	hits += [Hit("ssn", m.start(), m.end()) for m in _SSN.finditer(text) if _ssn_issuable(m.group(1), m.group(3), m.group(4))]
	hits += _card_hits(text)
	return sorted(hits, key=lambda h: h.start)


def entities(text: str) -> list[str]:
	"""Each kind of PII in the text once, in ``ENTITY_ORDER``."""
	kinds = {hit.entity for hit in find(normalize(text))}
	return [kind for kind in ENTITY_ORDER if kind in kinds]


def redact(text: str) -> str:
	"""``text`` with every hit replaced. Text with no hit comes back exactly as it was (normalization is only for looking)."""
	normalized = normalize(text)
	hits = find(normalized)
	if not hits:
		return text
	out, cursor = [], 0
	for hit in hits:
		if hit.start < cursor:  # overlapping hits: the earlier one already covered it
			continue
		out.append(normalized[cursor:hit.start])
		out.append(REDACTION)
		cursor = hit.end
	out.append(normalized[cursor:])
	return "".join(out)
