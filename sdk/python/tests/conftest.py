import pytest
import respx
import httpx


FAKE_API_KEY = "opai_testkey123"
BASE_URL = "https://api.openproxyai.com"


@pytest.fixture
def api_key():
    return FAKE_API_KEY


@pytest.fixture
def base_url():
    return BASE_URL
