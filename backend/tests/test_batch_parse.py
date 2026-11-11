"""Validating a batch input file: the whole file or nothing, and the first problem is named (Phase 5, slice 5.6)."""

from __future__ import annotations

import json

import pytest

from app.services import batch_service as bs


def line(custom_id="a", model="openai/gpt-4o-mini", content="hi", **body):
	return json.dumps({"custom_id": custom_id, "method": "POST", "url": "/v1/chat/completions", "body": {"model": model, "messages": [{"role": "user", "content": content}], **body}})


def parse(*lines):
	return bs.parse_input(("\n".join(lines)).encode())


def test_a_valid_file_parses_in_order_with_its_options():
	lines = parse(line("one"), "", line("two", temperature=0.5, max_tokens=20))
	assert [(l.idx, l.custom_id) for l in lines] == [(0, "one"), (1, "two")]
	assert (lines[1].temperature, lines[1].max_tokens, lines[0].messages) == (0.5, 20, [{"role": "user", "content": "hi"}])


@pytest.mark.parametrize("data,message", [
	(b"", "empty"), (b"   \n\n", "empty"), (b"\xff\xfe", "UTF-8"), (b"not json", "line 1 is not valid JSON"), (b"[1,2]", "must be an object"),
])
def test_malformed_files_are_refused_with_the_reason(data, message):
	with pytest.raises(bs.BatchFileError, match=message):
		bs.parse_input(data)


@pytest.mark.parametrize("bad,message", [
	({"custom_id": "", "method": "POST", "url": "/v1/chat/completions", "body": {}}, "custom_id"),
	({"custom_id": "x" * 65, "method": "POST", "url": "/v1/chat/completions", "body": {}}, "custom_id"),
	({"custom_id": 5, "method": "POST", "url": "/v1/chat/completions", "body": {}}, "custom_id"),
	({"custom_id": "a", "method": "GET", "url": "/v1/chat/completions", "body": {}}, "only"),
	({"custom_id": "a", "method": "POST", "url": "/v1/embeddings", "body": {}}, "only"),
	({"custom_id": "a", "method": "POST", "url": "/v1/chat/completions", "body": {}, "extra": 1}, "only"),
	({"custom_id": "a", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-4o", "messages": [{"role": "user", "content": "x"}]}}, "provider/name"),
	({"custom_id": "a", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "openai/m", "messages": []}}, "messages"),
	({"custom_id": "a", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "openai/m", "messages": [{"role": "tool", "content": "x"}]}}, "messages"),
	({"custom_id": "a", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "openai/m", "messages": [{"role": "user", "content": ["x"]}]}}, "messages"),
	({"custom_id": "a", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "openai/m", "messages": [{"role": "user", "content": "x"}], "stream": True}}, "not stream"),
	({"custom_id": "a", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "openai/m", "messages": [{"role": "user", "content": "x"}], "tools": []}}, "not tools"),
	({"custom_id": "a", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "openai/m", "messages": [{"role": "user", "content": "x"}], "temperature": 3}}, "temperature"),
	({"custom_id": "a", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "openai/m", "messages": [{"role": "user", "content": "x"}], "temperature": True}}, "temperature"),
	({"custom_id": "a", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "openai/m", "messages": [{"role": "user", "content": "x"}], "max_tokens": 0}}, "max_tokens"),
])
def test_a_line_that_is_not_a_complete_supported_request_is_refused_and_named(bad, message):
	with pytest.raises(bs.BatchFileError, match=f"line 2.*{message}|line 2: .*{message}"):
		bs.parse_input((line("first") + "\n" + json.dumps(bad)).encode())


def test_a_repeated_custom_id_is_refused():
	with pytest.raises(bs.BatchFileError, match="line 2.*used twice"):
		parse(line("same"), line("same"))


def test_the_line_count_and_size_limits_apply(monkeypatch):
	monkeypatch.setattr(bs, "MAX_LINES", 2)
	with pytest.raises(bs.BatchFileError, match="at most 2"):
		parse(line("a"), line("b"), line("c"))
	monkeypatch.setattr(bs, "MAX_LINE_BYTES", 50)
	with pytest.raises(bs.BatchFileError, match="longer than"):
		parse(line("a"))
	with pytest.raises(bs.BatchFileError, match="larger than"):
		bs.parse_input(b"x" * (bs.MAX_FILE_BYTES + 1))


def test_nothing_is_accepted_in_part():
	with pytest.raises(bs.BatchFileError):
		parse(line("ok1"), line("ok2"), "{bad")
