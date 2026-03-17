"""
Microsoft Presidio NLP-based PII analyzer.
Lazy-init singleton pattern — safe to import always.
Falls back gracefully if presidio-analyzer is not installed.
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_analyzer = None
_initialized = False


def _get_analyzer():
    global _analyzer, _initialized
    if _initialized:
        return _analyzer
    _initialized = True
    try:
        from presidio_analyzer import AnalyzerEngine
        _analyzer = AnalyzerEngine()
        logger.info("Presidio AnalyzerEngine initialized")
    except ImportError:
        logger.warning("presidio-analyzer not installed — PII detection falling back to regex")
        _analyzer = None
    return _analyzer


def is_enabled() -> bool:
    return _get_analyzer() is not None


def analyze(text: str, language: str = "en", entities: Optional[list[str]] = None) -> list:
    """
    Returns list of RecognizerResult. Empty list if Presidio not available.
    entities: optional filter list (e.g. ["EMAIL_ADDRESS", "US_SSN"])
    """
    analyzer = _get_analyzer()
    if analyzer is None:
        return []
    try:
        results = analyzer.analyze(text=text, language=language, entities=entities)
        return results
    except Exception as exc:
        logger.warning("Presidio analysis failed: %s", exc)
        return []
