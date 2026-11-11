#!/usr/bin/env python3
"""Checks the non-chat endpoints on a running seeded demo: images, speech, transcription and /v1/responses.

Standard library only. Run by scripts/smoke.sh; also runnable on its own (BASE_URL, FAKE_URL as in the other smoke scripts).

For each endpoint it asks what the *provider* received, not only what the client got back: the fake upstream records every call.
It always restores the demo (routing off, registry and key removed).
"""

import json
import os
import sys
import urllib.error
import urllib.request
import uuid

import smoke_lib
from smoke_lib import BASE, CLIENT_KEY, call, check, login_admin

FAKE_URL = os.environ.get("FAKE_URL", "http://localhost:9090").rstrip("/")


def upstream_calls(path):
    return [c for c in json.loads(urllib.request.urlopen(f"{FAKE_URL}/__calls", timeout=10).read()) if c["path"] == path]


def multipart(fields, filename, data):
    boundary = uuid.uuid4().hex
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items()]
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: audio/mpeg\r\n\r\n'.encode() + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def transcribe(model, *, filename="meeting.mp3", data=b"ID3-fake-audio" * 50, **fields):
    body, content_type = multipart({"model": model, **fields}, filename, data)
    request = urllib.request.Request(BASE + "/v1/audio/transcriptions", data=body, method="POST", headers={"Authorization": f"Bearer {CLIENT_KEY}", "Content-Type": content_type})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw, status = response.read(), response.status
    except urllib.error.HTTPError as error:
        raw, status = error.read(), error.code
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, raw


def main():
    admin = login_admin()
    _, _, existing = call("GET", "/api/v1/model-registry", token=admin)
    if existing:
        sys.exit("The model registry is not empty. This script is for the seeded demo (docker compose down -v resets it).")
    policy = lambda **fields: call("PATCH", "/api/v1/organizations/current/policy", token=admin, body=fields)  # noqa: E731
    post = lambda path, body: call("POST", path, token=CLIENT_KEY, body=body)  # noqa: E731
    entries, key_id = [], None
    try:
        status, _, key = call("POST", "/api/v1/provider-keys", token=admin, body={
            "provider": "openai", "api_key": "sk-smoke-modalities", "key_alias": "smoke-modalities", "api_base": "http://fake-llm:9090/v1",
            "is_internal": True, "max_data_class": "confidential", "weight": 1})
        check("a key for the fake upstream", status == 201, key)
        key_id = key["id"]
        # Every model is registered up front and routing is enforced, so each call is served through this key and no other
        # (without that the gateway may pick the demo's own key, which has no custom endpoint).
        for model, level in (("openai/dall-e-3", "internal"), ("openai/tts-1", "internal"), ("openai/whisper-1", "confidential"), ("openai/gpt-4o-mini", "internal")):
            status, _, entry = call("POST", "/api/v1/model-registry", token=admin, body={"model_id": model, "provider_key_id": key_id, "max_data_class": level, "regions": ["us"]})
            check(f"register {model} ({level})", status == 201, entry)
            entries.append(entry.get("id"))
        check("routing enforced", policy(routing_mode="enforce")[0] == 200)

        print("-- images")
        status, headers, body = post("/v1/images/generations", {"model": "openai/dall-e-3", "prompt": f"a lighthouse {uuid.uuid4().hex[:6]}", "response_format": "b64_json"})
        check("an image is generated and returned", status == 200 and body["data"][0]["b64_json"].startswith("iVBOR"), body)
        check("the call is gateway-stamped", headers.get("x-openproxyai-model") == "openai/dall-e-3" and "x-openproxyai-request-id" in headers, headers)
        status, _, body = post("/v1/images/generations", {"model": "openai/dall-e-3", "prompt": "x", "n": 9})
        check("more than 4 images is a 422", status == 422, body)

        print("-- speech")
        status, headers, body = call("POST", "/v1/audio/speech", token=CLIENT_KEY, body={"model": "openai/tts-1", "input": "Hello there", "voice": "alloy", "response_format": "wav"})
        check("speech returns audio bytes with the right type", status == 200 and headers.get("content-type") == "audio/wav" and "fake-audio" in str(body), (status, headers.get("content-type")))

        print("-- transcription (audio cannot be inspected)")
        status, body = transcribe("openai/whisper-1", language="en")
        check("a transcription is served and returns the transcript", status == 200 and "transcript of the recording" in body.get("text", ""), body)
        sent = upstream_calls("/v1/audio/transcriptions")
        check("the provider received the audio and the language", len(sent) >= 1 and sent[-1]["fields"].get("language") == "en" and sent[-1]["bytes"] > 700, sent[-1:] )
        check("a file that is not audio is a 422", transcribe("openai/whisper-1", filename="notes.txt")[0] == 422)
        check("an empty file is a 422", transcribe("openai/whisper-1", data=b"")[0] == 422)

        print("-- responses")
        prompt = f"summarize the report {uuid.uuid4().hex[:8]}"
        status, _, body = post("/v1/responses", {"model": "openai/gpt-4o-mini", "input": prompt})
        check("a response is returned", status == 200 and body["output"][0]["content"][0]["text"] == "fake response", body)
        sent = [c for c in upstream_calls("/v1/responses") if prompt in json.dumps(c["body"])]
        check("the provider was told store=false although the client did not say so", len(sent) == 1 and sent[0]["body"].get("store") is False, sent)
        status, _, body = post("/v1/responses", {"model": "openai/gpt-4o-mini", "input": "hi", "store": True})
        check("store=true is refused while provider state is not allowed (400)", status == 400 and body.get("error") == "provider_state_not_allowed", body)
        status, _, body = post("/v1/responses", {"model": "openai/gpt-4o-mini", "input": "hi", "tools": [{"type": "web_search"}]})
        check("a provider-run tool is refused (422)", status == 422, body)
        check("allowing provider state lets store=true through", policy(allow_provider_response_state=True)[0] == 200)
        status, _, body = post("/v1/responses", {"model": "openai/gpt-4o-mini", "input": f"keep it {uuid.uuid4().hex[:6]}", "store": True})
        check("and now it is sent as store=true", status == 200 and upstream_calls("/v1/responses")[-1]["body"].get("store") is True, body)
        policy(allow_provider_response_state=False)

        print("-- policy applies to every endpoint")
        check("blocked keyword set", policy(enforcement_mode="enforce", blocked_keywords=["falcon"])[0] == 200)
        for label, path, request in (
            ("images", "/v1/images/generations", {"model": "openai/dall-e-3", "prompt": "the falcon project"}),
            ("speech", "/v1/audio/speech", {"model": "openai/tts-1", "input": "the falcon project", "voice": "alloy"}),
            ("responses", "/v1/responses", {"model": "openai/gpt-4o-mini", "input": "the falcon project"}),
        ):
            before = len(upstream_calls(path))
            status, _, body = post(path, request)
            check(f"{label}: a blocked keyword is a 446 and never reaches the provider", status == 446 and len(upstream_calls(path)) == before, (status, body))
        status, body = transcribe("openai/whisper-1", prompt="the falcon project")
        check("transcription: the hint text is scanned too (446)", status == 446, (status, body))
        policy(enforcement_mode="off", blocked_keywords=[])

        print("-- routing applies to every endpoint")
        status, _, body = post("/v1/responses", {"model": "openai/gpt-4o-mini", "input": f"routine {uuid.uuid4().hex[:6]}"})
        check("a text request to an internal model is served", status == 200, body)
        status, _, body = post("/v1/images/generations", {"model": "openai/dall-e-2", "prompt": "unregistered"})
        check("an unregistered image model is refused (446)", status == 446 and body.get("route_reason") == "not_in_registry", body)
        status, _, entry = call("PATCH", f"/api/v1/model-registry/{entries[2]}", token=admin, body={"max_data_class": "internal"})
        check("the transcription model is now cleared only for internal data", status == 200, entry)
        before = len(upstream_calls("/v1/audio/transcriptions"))
        status, body = transcribe("openai/whisper-1")
        check("audio is uninspected, so it is refused (446) and never reaches that model", status == 446 and len(upstream_calls("/v1/audio/transcriptions")) == before, (status, body))
        status, _, entry = call("PATCH", f"/api/v1/model-registry/{entries[2]}", token=admin, body={"max_data_class": "confidential"})
        check("clearing it for confidential data again", status == 200, entry)
        status, body = transcribe("openai/whisper-1")
        check("then the same upload is served", status == 200, (status, body))

        print("-- the audit log")
        _, _, logs = call("GET", "/api/v1/analytics/logs?limit=50", token=admin)
        models = {row["model"] for row in logs["items"]}
        check("every endpoint left an audit row", {"openai/dall-e-3", "openai/tts-1", "openai/whisper-1", "openai/gpt-4o-mini"} <= models, models)
    finally:
        policy(routing_mode="off", enforcement_mode="off", blocked_keywords=[], allow_provider_response_state=False)
        for entry_id in entries:
            if entry_id:
                call("DELETE", f"/api/v1/model-registry/{entry_id}", token=admin)
        if key_id:
            call("DELETE", f"/api/v1/provider-keys/{key_id}", token=admin)

    if smoke_lib.failures:
        print(f"{smoke_lib.failures} modality check(s) failed")
        sys.exit(1)
    print("modalities smoke passed")


if __name__ == "__main__":
    main()
