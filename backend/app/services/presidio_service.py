"""
Regex-based PII detection (active by default).
Presidio NLP is available but disabled by default due to image size (+800MB) —
uncomment presidio-analyzer in requirements.txt to enable.
Lazy-init singleton pattern — safe to import always.
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
        logger.info("presidio-analyzer not installed — regex-based PII detection is active (uncomment presidio-analyzer in requirements.txt to enable NLP)")
        _analyzer = None
    return _analyzer


def is_enabled() -> bool:
    return _get_analyzer() is not None


def analyze(text: str, language: str = "en", entities: Optional[list[str]] = None) -> list:
    """
    Returns list of RecognizerResult. Empty list only if Presidio NLP is not enabled (default).
    Raises on runtime errors — caller must handle or let propagate as 500.
    entities: optional filter list (e.g. ["EMAIL_ADDRESS", "US_SSN"])
    """
    analyzer = _get_analyzer()
    if analyzer is None:
        return []
    return analyzer.analyze(text=text, language=language, entities=entities)
