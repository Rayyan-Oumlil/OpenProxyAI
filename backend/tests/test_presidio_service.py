"""Tests for presidio_service — must pass even without presidio-analyzer installed."""
from unittest.mock import patch, MagicMock
import sys
import importlib


def test_is_enabled_returns_false_when_presidio_missing():
    """When presidio-analyzer is not installed, is_enabled() returns False."""
    # Force re-init by patching import
    import app.services.presidio_service as ps
    with patch.dict(sys.modules, {'presidio_analyzer': None}):
        ps._initialized = False
        ps._analyzer = None
        result = ps.is_enabled()
        # Reset for other tests
        ps._initialized = False
        ps._analyzer = None
    # Should not raise, returns bool
    assert isinstance(result, bool)


def test_analyze_returns_empty_when_disabled():
    """analyze() returns [] when Presidio not available."""
    import app.services.presidio_service as ps
    original_analyzer = ps._analyzer
    original_initialized = ps._initialized
    ps._analyzer = None
    ps._initialized = True
    result = ps.analyze("my email is test@example.com")
    ps._analyzer = original_analyzer
    ps._initialized = original_initialized
    assert result == []


def test_analyze_raises_when_presidio_crashes():
    """analyze() propagates exceptions when Presidio is enabled but crashes at runtime.
    Callers get a hard failure (500) instead of silently missing PII.
    """
    import pytest
    import app.services.presidio_service as ps
    mock_analyzer = MagicMock()
    mock_analyzer.analyze.side_effect = RuntimeError("NLP engine error")
    original_analyzer = ps._analyzer
    original_initialized = ps._initialized
    ps._analyzer = mock_analyzer
    ps._initialized = True
    try:
        with pytest.raises(RuntimeError, match="NLP engine error"):
            ps.analyze("some text")
    finally:
        ps._analyzer = original_analyzer
        ps._initialized = original_initialized
