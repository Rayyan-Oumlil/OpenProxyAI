"""One definition of an org's data region."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.utils.region import org_data_region, region_of


@pytest.mark.parametrize(
	"org,expected",
	[(None, "us"), (SimpleNamespace(data_region=None), "us"), (SimpleNamespace(data_region="  "), "us"), (SimpleNamespace(data_region=" EU "), "eu"),
	 (SimpleNamespace(data_region="ap"), "ap"), (MagicMock(), "us")],  # a mock's attribute is not a string
)
def test_region_of(org, expected):
	assert region_of(org) == expected


async def test_org_data_region_accepts_an_id_as_uuid_or_string():
	org_id = uuid4()
	db = MagicMock()
	db.get = AsyncMock(return_value=SimpleNamespace(data_region="eu"))
	assert await org_data_region(db, org_id) == "eu"
	assert await org_data_region(db, str(org_id)) == "eu"
	assert db.get.call_args.args[1] == org_id
