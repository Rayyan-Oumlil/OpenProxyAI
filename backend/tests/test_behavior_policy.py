"""Behaviour defaults and ceiling as policy: stored, validated, and read back safely."""

import pytest
from pydantic import ValidationError

from app.schemas.policy import BehaviorCeiling, BehaviorDefaults, PolicyConfigRequest
from app.services import behavior as bh
from app.services.policy_service import PolicyConfig


def test_stored_settings_round_trip():
	config = PolicyConfig(behavior_defaults={"creativity": "medium", "citations": True}, behavior_ceiling={"max_response_length": "long"})
	again = PolicyConfig.from_dict(config.to_dict())
	assert again.behavior_defaults == {"creativity": "medium", "citations": True}
	assert again.behavior_ceiling == {"max_response_length": "long"}


def test_an_org_that_never_set_them_has_neither():
	config = PolicyConfig.from_dict({})
	assert config.behavior_defaults == {} and config.behavior_ceiling == {}
	assert bh.settle(config.behavior_defaults, config.behavior_ceiling, bh.Behavior()) is None  # the old code path, untouched


def test_corrupt_stored_values_are_dropped_not_guessed():
	config = PolicyConfig.from_dict({"behavior_ceiling": {"creativity": "extreme", "reasoning_depth": "low", "citations": True}, "behavior_defaults": "x"})
	assert config.behavior_ceiling == {"reasoning_depth": "low"}  # an unreadable entry is no ceiling; a ceiling never holds citations
	assert config.behavior_defaults == {}


def test_the_api_accepts_known_words_only():
	assert BehaviorDefaults(creativity="low", citations=True).model_dump(exclude_none=True) == {"creativity": "low", "citations": True}
	for bad in ({"creativity": "wild"}, {"max_response_length": "low"}, {"tone": "formal"}):
		with pytest.raises(ValidationError):
			BehaviorDefaults(**bad)


def test_a_ceiling_cannot_carry_citations():
	with pytest.raises(ValidationError):
		BehaviorCeiling(citations=True)


def test_null_is_refused_so_it_cannot_silently_clear_a_ceiling():
	with pytest.raises(ValidationError):
		PolicyConfigRequest(behavior_ceiling=None)
	assert PolicyConfigRequest(behavior_ceiling={}).model_dump(exclude_unset=True) == {"behavior_ceiling": {}}
