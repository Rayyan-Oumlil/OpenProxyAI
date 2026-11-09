"""The one PII detector behind policy blocking, response redaction and data classification."""

import pytest

from app.services import pii_detection as pii


@pytest.mark.parametrize(
	"text,expected",
	[
		("my ssn 123-45-6789", ["ssn"]),
		("my ssn 123 45 6789", ["ssn"]),
		("my ssn 123.45.6789", ["ssn"]),
		("my ssn １２３-４５-６７８９", ["ssn"]),  # fullwidth digits
		("my ssn 123-45-​6789", ["ssn"]),  # a zero-width space slipped into the middle
		("my ssn 123­-45-6789", ["ssn"]),  # soft hyphen
		("card 4111 1111 1111 1111", ["payment_card"]),
		("card 4111-1111-1111-1111", ["payment_card"]),
		("card 4111111111111111", ["payment_card"]),
		("card 3782 822463 10005", ["payment_card"]),  # American Express
		("card ４１１１ １１１１ １１１１ １１１１", ["payment_card"]),
		("write to jane@example.com", ["email"]),
		("write to jane＠example.com", ["email"]),  # fullwidth @
		("jane@example.com, 123-45-6789 and 4111111111111111", ["email", "ssn", "payment_card"]),
	],
)
def test_it_finds_pii_however_it_is_formatted(text, expected):
	assert pii.entities(text) == expected


@pytest.mark.parametrize(
	"text",
	[
		"What is the capital of France?",
		"order number 1234 5678 9012 3456",  # 16 digits, but not a valid card number
		"call 514-555-0199",  # a phone number is not in the built-in set
		"version 1.2.3 build 20241103",
		"ticket 000-12-3456",  # an SSN never starts with 000
		"ticket 666-12-3456",  # ... or 666
		"ticket 923-12-3456",  # ... or 9xx
		"ticket 123-00-6789",  # a group is never 00
		"ticket 123-45-0000",  # a serial is never 0000
		"write to jane [at] example [dot] com",  # deliberately spelled-out: not detected (documented)
		"my ssn 123456789",  # nine bare digits are too ambiguous to call an SSN
	],
)
def test_it_leaves_ordinary_text_alone(text):
	assert pii.entities(text) == []


def test_entities_are_distinct_and_in_a_fixed_order():
	assert pii.entities("123-45-6789 and 123-45-6789 and jane@example.com") == ["email", "ssn"]


def test_a_card_must_pass_the_luhn_check_and_have_a_plausible_length():
	assert pii.luhn_valid("4111111111111111") and pii.luhn_valid("378282246310005")
	assert not pii.luhn_valid("4111111111111112") and not pii.luhn_valid("")
	assert pii.entities("number 4111111111111") == []  # 13 digits but fails Luhn
	assert pii.entities("number 79927398713") == []  # Luhn-valid but only 11 digits


def test_redaction_replaces_what_was_detected_and_nothing_else():
	text = "Write to jane@example.com about ticket 1234 5678 9012 3456, SSN 123 45 6789, card 4111 1111 1111 1111."
	assert pii.redact(text) == "Write to [REDACTED] about ticket 1234 5678 9012 3456, SSN [REDACTED], card [REDACTED]."


def test_redaction_catches_what_detection_catches():
	for text in ("ssn 123.45.6789", "ssn 123-45-​6789", "mail jane＠example.com", "card ４１１１ １１１１ １１１１ １１１１"):
		assert pii.entities(text) and "[REDACTED]" in pii.redact(text), text


def test_text_without_pii_comes_back_untouched_even_if_it_has_odd_characters():
	text = "fullwidth Ｈｅｌｌｏ and a ligature ﬁne ​ zero-width"
	assert pii.redact(text) == text  # normalization is only used to look, and only changes the output when it redacts


def test_normalization_removes_invisible_characters_and_folds_compatibility_forms():
	assert pii.normalize("１２３​-４５") == "123-45"
	assert pii.normalize("a‮b﻿c") == "abc"  # bidi override and byte-order mark
