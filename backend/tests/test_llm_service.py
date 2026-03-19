"""Unit tests for llm_service helper functions — pure logic, no live dependencies."""

import json
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services.llm_service import _is_retryable, _parse_labels, _split_model, _to_jsonable


# ── _split_model ────────────────────────────────────────────────────────


class TestSplitModel:
    def test_valid_model_splits_correctly(self):
        assert _split_model("openai/gpt-4") == ("openai", "gpt-4")

    def test_valid_model_with_multiple_slashes(self):
        provider, model = _split_model("azure/gpt-4/turbo")
        assert provider == "azure"
        assert model == "gpt-4/turbo"

    def test_no_slash_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            _split_model("invalid")
        assert exc_info.value.status_code == 400

    def test_only_slash_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            _split_model("/")
        assert exc_info.value.status_code == 400

    def test_empty_provider_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            _split_model("/gpt-4")
        assert exc_info.value.status_code == 400

    def test_empty_model_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            _split_model("openai/")
        assert exc_info.value.status_code == 400


# ── _to_jsonable ────────────────────────────────────────────────────────


class TestToJsonable:
    def test_dict_passthrough(self):
        d = {"key": "value", "n": 42}
        assert _to_jsonable(d) is d

    def test_list_passthrough(self):
        lst = [1, 2, 3]
        assert _to_jsonable(lst) is lst

    def test_none_passthrough(self):
        assert _to_jsonable(None) is None

    def test_string_passthrough(self):
        assert _to_jsonable("hello") == "hello"

    def test_bool_passthrough(self):
        assert _to_jsonable(True) is True

    def test_object_with_model_dump(self):
        obj = MagicMock()
        obj.model_dump.return_value = {"a": 1}
        result = _to_jsonable(obj)
        obj.model_dump.assert_called_once_with(exclude_none=True)
        assert result == {"a": 1}

    def test_object_with_dict_method(self):
        obj = MagicMock(spec=[])
        obj.dict = MagicMock(return_value={"b": 2})
        obj.model_dump = None
        del obj.model_dump
        result = _to_jsonable(obj)
        assert result == {"b": 2}

    def test_decimal_serialised_via_default_str(self):
        result = _to_jsonable(Decimal("1.23"))
        assert result == "1.23" or result == 1.23


# ── _parse_labels ───────────────────────────────────────────────────────


def _make_request(headers: dict | None = None) -> MagicMock:
    req = MagicMock()
    req.headers = headers or {}
    return req


class TestParseLabels:
    def test_none_when_header_absent(self):
        assert _parse_labels(_make_request()) is None

    def test_none_when_header_empty(self):
        assert _parse_labels(_make_request({"x-openproxy-labels": ""})) is None

    def test_valid_json_returns_dict(self):
        labels = _parse_labels(
            _make_request({"x-openproxy-labels": '{"env": "prod", "team": "ml"}'})
        )
        assert labels == {"env": "prod", "team": "ml"}

    def test_invalid_json_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            _parse_labels(_make_request({"x-openproxy-labels": "not json"}))
        assert exc_info.value.status_code == 400

    def test_non_object_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            _parse_labels(_make_request({"x-openproxy-labels": '["a","b"]'}))
        assert exc_info.value.status_code == 400

    def test_more_than_10_keys_raises_400(self):
        labels = {f"k{i}": f"v{i}" for i in range(11)}
        with pytest.raises(HTTPException) as exc_info:
            _parse_labels(_make_request({"x-openproxy-labels": json.dumps(labels)}))
        assert exc_info.value.status_code == 400

    def test_non_string_values_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            _parse_labels(_make_request({"x-openproxy-labels": '{"count": 42}'}))
        assert exc_info.value.status_code == 400

    def test_key_too_long_raises_400(self):
        long_key = "k" * 65
        with pytest.raises(HTTPException) as exc_info:
            _parse_labels(
                _make_request({"x-openproxy-labels": json.dumps({long_key: "v"})})
            )
        assert exc_info.value.status_code == 400

    def test_value_too_long_raises_400(self):
        long_val = "v" * 65
        with pytest.raises(HTTPException) as exc_info:
            _parse_labels(
                _make_request({"x-openproxy-labels": json.dumps({"k": long_val})})
            )
        assert exc_info.value.status_code == 400

    def test_exactly_10_keys_is_ok(self):
        labels = {f"k{i}": f"v{i}" for i in range(10)}
        result = _parse_labels(
            _make_request({"x-openproxy-labels": json.dumps(labels)})
        )
        assert len(result) == 10


# ── _is_retryable ──────────────────────────────────────────────────────


class TestIsRetryable:
    @pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
    def test_retryable_status_codes(self, code):
        exc = Exception("fail")
        exc.status_code = code
        assert _is_retryable(exc) is True

    @pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
    def test_non_retryable_status_codes(self, code):
        exc = Exception("fail")
        exc.status_code = code
        assert _is_retryable(exc) is False

    def test_no_status_code_returns_false(self):
        assert _is_retryable(Exception("no attr")) is False

    def test_non_int_status_code_returns_false(self):
        exc = Exception("fail")
        exc.status_code = "500"
        assert _is_retryable(exc) is False
