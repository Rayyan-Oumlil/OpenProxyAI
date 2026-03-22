"""Tests for air-gap mode (AIRGAP_MODE, LICENSE_KEY) — Data Residency Tier 2."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_airgap_mode_off_no_license_required():
    """Without AIRGAP_MODE, LICENSE_KEY is optional."""
    settings = Settings.model_validate({
        "AIRGAP_MODE": False,
        "LICENSE_KEY": "",
    })
    assert settings.AIRGAP_MODE is False
    assert settings.LICENSE_KEY == ""


def test_airgap_mode_on_requires_valid_license():
    """AIRGAP_MODE=true with valid LICENSE_KEY succeeds."""
    settings = Settings.model_validate({
        "AIRGAP_MODE": True,
        "LICENSE_KEY": "opai-0123456789abcdef",
    })
    assert settings.AIRGAP_MODE is True
    assert len(settings.LICENSE_KEY) >= 16


def test_airgap_mode_on_rejects_empty_license():
    """AIRGAP_MODE=true with empty LICENSE_KEY fails at validation."""
    with pytest.raises(ValidationError) as exc_info:
        Settings.model_validate({
            "AIRGAP_MODE": True,
            "LICENSE_KEY": "",
        })
    assert "LICENSE_KEY" in str(exc_info.value) or "AIRGAP" in str(exc_info.value)


def test_airgap_mode_on_rejects_short_license():
    """AIRGAP_MODE=true with LICENSE_KEY < 16 chars fails."""
    with pytest.raises(ValidationError):
        Settings.model_validate({
            "AIRGAP_MODE": True,
            "LICENSE_KEY": "short",
        })
