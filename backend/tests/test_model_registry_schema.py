"""Model registry request validation (no database)."""

import pytest
from pydantic import ValidationError

from app.schemas.model_registry import ModelRegistryCreate, ModelRegistryUpdate


def _create(**overrides):
	return ModelRegistryCreate(**{"model_id": "openai/gpt-4o", "regions": ["us"], **overrides})


def test_minimal_entry_has_safe_defaults():
	entry = _create()
	assert entry.max_data_class == "internal"
	assert entry.risk_rating == "medium"
	assert entry.trains_on_data is False
	assert entry.enabled is True
	assert entry.capabilities == []
	assert entry.provider_key_id is None


def test_regions_are_required_and_must_be_known():
	with pytest.raises(ValidationError):
		ModelRegistryCreate(model_id="openai/gpt-4o")
	with pytest.raises(ValidationError):
		_create(regions=[])
	with pytest.raises(ValidationError):
		_create(regions=["mars"])


@pytest.mark.parametrize("model_id", ["gpt-4o", "/gpt-4o", "openai/", "open ai/gpt", "openai/gpt 4", "a" * 201])
def test_model_id_must_look_like_provider_slash_model(model_id):
	with pytest.raises(ValidationError):
		_create(model_id=model_id)


@pytest.mark.parametrize("model_id", ["openai/gpt-4o", "anthropic/claude-3-5-sonnet-20241022", "ollama/llama3:70b", "azure/my-deployment"])
def test_common_model_ids_are_accepted(model_id):
	assert _create(model_id=model_id).model_id == model_id


def test_capabilities_are_upper_snake_unique_and_bounded():
	assert _create(capabilities=["CODE_GENERATION", "VISION"]).capabilities == ["CODE_GENERATION", "VISION"]
	for bad in (["code"], ["CODE GEN"], ["CODE_GENERATION", "CODE_GENERATION"], [f"C{i}" for i in range(21)]):
		with pytest.raises(ValidationError):
			_create(capabilities=bad)


def test_numeric_and_enum_fields_are_bounded():
	for bad in ({"retention_days": -1}, {"retention_days": 4000}, {"risk_rating": "extreme"}, {"max_data_class": "top-secret"}, {"cost_tier": "free"}):
		with pytest.raises(ValidationError):
			_create(**bad)
	assert _create(retention_days=0).retention_days == 0


def test_update_cannot_change_the_model_id_or_null_required_fields():
	with pytest.raises(ValidationError):
		ModelRegistryUpdate(model_id="openai/other")
	for field in ("regions", "max_data_class", "risk_rating", "trains_on_data", "enabled", "capabilities"):
		with pytest.raises(ValidationError):
			ModelRegistryUpdate(**{field: None})
	assert ModelRegistryUpdate(provider_key_id=None).model_dump(exclude_unset=True) == {"provider_key_id": None}
	assert ModelRegistryUpdate(owner=None, retention_days=None).model_dump(exclude_unset=True) == {"owner": None, "retention_days": None}
