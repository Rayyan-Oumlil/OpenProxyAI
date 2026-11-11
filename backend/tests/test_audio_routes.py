"""The audio HTTP routes: authentication first, upload limits, and what reaches the pipeline (Phase 5, slice 5.4)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.responses import JSONResponse

from app.dependencies import get_current_user_from_api_key, get_db, get_redis, get_request_id
from app.main import app
from app.routes import proxy as proxy_routes
from app.schemas import modalities
from tests.conftest import FakeDB

URL = "/v1/audio/transcriptions"
AUDIO = b"fake-audio-bytes" * 8


@pytest.fixture
def wired(client, fake_redis, monkeypatch):
	"""The routes with auth replaced and the pipeline replaced by a recorder of what it was handed."""
	seen = SimpleNamespace(requests=[], modalities=[])
	user = SimpleNamespace(id=uuid4(), org_id=uuid4(), is_active=True)

	async def auth():
		return user, SimpleNamespace(id=uuid4(), org_id=user.org_id, user=user)

	async def db():
		yield FakeDB()

	async def redis():
		return fake_redis

	async def request_id():
		return uuid4().hex

	async def pipeline(modality, request, **_kwargs):
		seen.requests.append(request)
		seen.modalities.append(modality)
		return JSONResponse({"text": "ok"})

	app.dependency_overrides[get_current_user_from_api_key] = auth
	app.dependency_overrides[get_db] = db
	app.dependency_overrides[get_redis] = redis
	app.dependency_overrides[get_request_id] = request_id
	monkeypatch.setattr(proxy_routes, "run_modality", pipeline)
	seen.client = client
	return seen


def upload(wired, *, data=AUDIO, filename="meeting.mp3", **fields):
	return wired.client.post(URL, headers={"Authorization": "Bearer opai_dev_test"}, data={"model": "openai/whisper-1", **fields}, files={"file": (filename, data, "audio/mpeg")})


def test_a_valid_upload_reaches_the_pipeline_with_the_audio_and_its_options(wired):
	response = upload(wired, language="en", prompt="names: Alice", temperature="0.2", response_format="verbose_json")
	assert response.status_code == 200
	request = wired.requests[0]
	assert (request.model, request.filename, request.data, request.language, request.prompt, request.temperature, request.response_format) == (
		"openai/whisper-1", "meeting.mp3", AUDIO, "en", "names: Alice", 0.2, "verbose_json",
	)
	assert wired.modalities[0].opaque_input(request) is True


def test_an_upload_without_credentials_is_refused_before_anything_is_read(client, monkeypatch):
	called = []

	async def pipeline(*_a, **_k):
		called.append(1)

	monkeypatch.setattr(proxy_routes, "run_modality", pipeline)
	response = client.post(URL, data={"model": "openai/whisper-1"}, files={"file": ("a.mp3", AUDIO, "audio/mpeg")})
	assert response.status_code in (401, 403) and called == []


def test_a_file_over_the_limit_is_a_413_and_never_reaches_the_pipeline(wired, monkeypatch):
	monkeypatch.setattr(proxy_routes, "MAX_AUDIO_BYTES", 100)
	monkeypatch.setattr(proxy_routes, "_MULTIPART_OVERHEAD_BYTES", 10)
	response = upload(wired, data=b"x" * 5_000)
	assert response.status_code == 413 and response.json()["error"] == "file_too_large" and wired.requests == []


def test_the_declared_length_is_enforced_even_when_the_file_part_is_small(wired, monkeypatch):
	"""A request that declares a huge body is refused on the header alone, before the form is parsed."""
	monkeypatch.setattr(proxy_routes, "MAX_AUDIO_BYTES", 100)
	monkeypatch.setattr(proxy_routes, "_MULTIPART_OVERHEAD_BYTES", 10)
	response = wired.client.post(URL, headers={"Authorization": "Bearer x", "Content-Length": "999999", "Content-Type": "multipart/form-data; boundary=x"}, content=b"--x--")
	assert response.status_code in (413, 400) and wired.requests == []


@pytest.mark.parametrize("filename", ["notes.txt", "evil.exe", "noextension", "../../etc/passwd.mp3.sh"])
def test_a_file_that_is_not_audio_is_a_422(wired, filename):
	assert upload(wired, filename=filename).status_code == 422 and wired.requests == []


def test_an_empty_file_and_a_missing_file_are_422s(wired):
	assert upload(wired, data=b"").status_code == 422
	response = wired.client.post(URL, headers={"Authorization": "Bearer x"}, data={"model": "openai/whisper-1"})
	assert response.status_code in (411, 422) and wired.requests == []


@pytest.mark.parametrize("fields", [{"language": "english"}, {"temperature": "hot"}, {"temperature": "5"}, {"response_format": "xml"}])
def test_bad_options_are_422s_with_a_reason(wired, fields):
	response = upload(wired, **fields)
	assert response.status_code == 422 and response.json()["error"] == "invalid_request" and wired.requests == []


def test_speech_goes_through_the_pipeline_with_a_modality_for_its_format(wired):
	response = wired.client.post("/v1/audio/speech", headers={"Authorization": "Bearer x"}, json={"model": "openai/tts-1", "input": "hello", "voice": "alloy", "response_format": "opus"})
	assert response.status_code == 200 and wired.requests[0].input == "hello" and wired.modalities[0].render is not None


def test_the_size_limit_is_the_one_the_schema_enforces_too():
	assert proxy_routes.MAX_AUDIO_BYTES == modalities.MAX_AUDIO_BYTES == 25 * 1024 * 1024


def test_an_upload_with_no_declared_length_is_a_411_so_the_size_check_cannot_be_skipped(wired):
	body = iter([b"--x\r\n", b"--x--\r\n"])  # a generator body is sent chunked, with no Content-Length
	response = wired.client.post(URL, headers={"Authorization": "Bearer x", "Content-Type": "multipart/form-data; boundary=x"}, content=body)
	assert response.status_code == 411 and response.json()["error"] == "length_required" and wired.requests == []


def test_the_file_is_checked_again_after_reading_in_case_the_declared_length_was_a_lie(wired, monkeypatch):
	monkeypatch.setattr(proxy_routes, "MAX_AUDIO_BYTES", 100)
	monkeypatch.setattr(proxy_routes, "_MULTIPART_OVERHEAD_BYTES", 10_000_000)  # the header check passes; only the read check can stop it
	response = upload(wired, data=b"x" * 5_000)
	assert response.status_code == 413 and wired.requests == []
