import httpx
import pytest
import respx

from openproxy import AsyncOpenProxy, OpenProxy, PolicyViolationError

BASE = "https://api.openproxyai.com"


@respx.mock
def test_models_list():
    respx.get(f"{BASE}/v1/models").mock(return_value=httpx.Response(200, json={"data": [{"id": "openai/gpt-4o"}]}))
    assert OpenProxy(api_key="k").models.list()["data"][0]["id"] == "openai/gpt-4o"


@respx.mock
def test_rerank_sends_only_set_fields():
    route = respx.post(f"{BASE}/v1/rerank").mock(return_value=httpx.Response(200, json={"results": []}))
    OpenProxy(api_key="k").rerank.create("cohere/rerank", "q", ["a", "b"], top_n=1)
    body = route.calls[0].request.content
    assert b'"top_n":1' in body.replace(b" ", b"") and b'"query"' in body


@respx.mock
def test_images_generate():
    route = respx.post(f"{BASE}/v1/images/generations").mock(return_value=httpx.Response(200, json={"data": []}))
    OpenProxy(api_key="k").images.generate("openai/gpt-image-1", "a cat", n=2)
    assert b'"n":2' in route.calls[0].request.content.replace(b" ", b"")


@respx.mock
def test_speech_returns_bytes():
    respx.post(f"{BASE}/v1/audio/speech").mock(return_value=httpx.Response(200, content=b"\x00\x01audio"))
    assert OpenProxy(api_key="k").audio.speech("openai/tts-1", "hi", "alloy") == b"\x00\x01audio"


@respx.mock
def test_transcribe_is_multipart():
    route = respx.post(f"{BASE}/v1/audio/transcriptions").mock(return_value=httpx.Response(200, json={"text": "hi"}))
    out = OpenProxy(api_key="k").audio.transcribe("openai/whisper-1", ("a.wav", b"RIFF"), language="en")
    request = route.calls[0].request
    assert out["text"] == "hi"
    assert request.headers["content-type"].startswith("multipart/form-data; boundary=")
    assert b'filename="a.wav"' in request.content and b'name="language"' in request.content


@respx.mock
def test_responses_create():
    respx.post(f"{BASE}/v1/responses").mock(return_value=httpx.Response(200, json={"id": "resp_1"}))
    assert OpenProxy(api_key="k").responses.create("openai/gpt-4o", "hello")["id"] == "resp_1"


@respx.mock
def test_feedback_drops_unset_fields():
    route = respx.post(f"{BASE}/v1/feedback").mock(return_value=httpx.Response(200, json={"score_name": "thumbs"}))
    OpenProxy(api_key="k").feedback.create("11111111-1111-1111-1111-111111111111", thumbs="up")
    body = route.calls[0].request.content
    assert b'"thumbs"' in body and b"comment" not in body and b'"value"' not in body


@respx.mock
def test_files_and_batches_flow():
    respx.post(f"{BASE}/v1/files").mock(return_value=httpx.Response(200, json={"id": "f1"}))
    batch = respx.post(f"{BASE}/v1/batches").mock(return_value=httpx.Response(200, json={"id": "b1", "status": "validating"}))
    respx.get(f"{BASE}/v1/batches").mock(return_value=httpx.Response(200, json={"data": []}))
    respx.post(f"{BASE}/v1/batches/b1/cancel").mock(return_value=httpx.Response(200, json={"status": "cancelled"}))
    respx.get(f"{BASE}/v1/files/f1/content").mock(return_value=httpx.Response(200, content=b'{"x":1}\n'))
    client = OpenProxy(api_key="k")
    file_id = client.files.create(b'{"custom_id":"1"}\n')["id"]
    assert client.batches.create(file_id, max_cost_usd=2.5)["id"] == "b1"
    assert b'"max_cost_usd":2.5' in batch.calls[0].request.content.replace(b" ", b"")
    assert client.batches.list(limit=5)["data"] == []
    assert client.batches.cancel("b1")["status"] == "cancelled"
    assert client.files.content("f1") == b'{"x":1}\n'


@respx.mock
def test_policy_block_carries_explanation():
    body = {"error": "policy_violation", "reason_code": "pii_detected", "detail": "blocked", "explanation": "That contains personal data."}
    respx.post(f"{BASE}/v1/responses").mock(return_value=httpx.Response(446, json=body))
    with pytest.raises(PolicyViolationError) as caught:
        OpenProxy(api_key="k").responses.create("openai/gpt-4o", "x")
    assert caught.value.explanation == "That contains personal data."


@respx.mock
@pytest.mark.asyncio
async def test_async_batches_and_feedback():
    respx.post(f"{BASE}/v1/batches").mock(return_value=httpx.Response(200, json={"id": "b2"}))
    respx.post(f"{BASE}/v1/feedback").mock(return_value=httpx.Response(200, json={"ok": True}))
    client = AsyncOpenProxy(api_key="k")
    assert (await client.batches.create("f1"))["id"] == "b2"
    assert (await client.feedback.create("11111111-1111-1111-1111-111111111111", value=1.0, score_name="quality"))["ok"]
