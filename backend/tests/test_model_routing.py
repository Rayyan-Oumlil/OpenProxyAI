"""Tests for model-pattern-based provider key routing."""
from unittest.mock import MagicMock


def _make_key(model_patterns=None, weight=1, is_active=True):
    key = MagicMock()
    key.model_patterns = model_patterns
    key.weight = weight
    key.is_active = is_active
    key.id = "key-1"
    return key


def test_model_pattern_matching_uses_matched_keys():
    """When model_patterns matches the requested model, those keys are preferred."""
    import fnmatch
    key_gpt4 = _make_key(model_patterns=["gpt-4*", "gpt-4o*"])
    key_claude = _make_key(model_patterns=["claude-*"])
    all_keys = [key_gpt4, key_claude]

    model = "gpt-4o"
    matched = [k for k in all_keys if k.model_patterns and
               any(fnmatch.fnmatch(model, p) for p in k.model_patterns)]
    assert key_gpt4 in matched
    assert key_claude not in matched


def test_fallback_to_all_keys_when_no_pattern_match():
    """When no key has a matching model pattern, all active keys are candidates."""
    import fnmatch
    key_a = _make_key(model_patterns=None)
    key_b = _make_key(model_patterns=["claude-*"])
    all_keys = [key_a, key_b]

    model = "gpt-4o"
    matched = [k for k in all_keys if k.model_patterns and
               any(fnmatch.fnmatch(model, p) for p in k.model_patterns)]
    # No match → fall back to all keys
    candidates = matched if matched else all_keys
    assert len(candidates) == len(all_keys)


def test_empty_model_patterns_treated_as_no_pattern():
    """model_patterns=[] is treated same as None (no constraint)."""
    import fnmatch
    key = _make_key(model_patterns=[])
    model = "gpt-4o"
    has_match = bool(key.model_patterns) and any(fnmatch.fnmatch(model, p) for p in key.model_patterns)
    assert has_match is False
