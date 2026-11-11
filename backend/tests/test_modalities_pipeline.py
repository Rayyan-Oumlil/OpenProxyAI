"""The guarantees every non-chat endpoint shares, proven once per modality (Phase 5).

Each case sends a request through the shared pipeline with the provider faked, and asks the same questions: is what the provider
received exactly what policy allowed, is a refusal a refusal, is the call audited. A new modality is added to ``CASES`` and inherits
the whole suite.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.schemas.modalities import ImageRequest, RerankRequest, ResponsesRequest, SpeechRequest, TranscriptionRequest
from app.services import llm_service as llm_module
from app.services import rate_limiter
from app.services.llm_service import ProviderKeyCandidate, llm_service
from app.services.modalities import IMAGES, RERANK, RESPONSES, TRANSCRIPTION, speech_modality
from app.services.modality_pipeline import run_modality
from app.services.policy_service import PolicyConfig, policy_store
from tests.test_embeddings_pipeline import entry

ORG, USER, KEY = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

RERANK_REPLY = {"id": "r1", "results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.2}], "meta": {"tokens": {"input_tokens": 21}}}


def rerank_request(model, text):
	return RerankRequest(model=model, query="which is best?", documents=["first doc", text])


# modality, request factory (model, text), provider function on llm_service, provider reply, default model
IMAGE_B64 = "iVBORw0KGgo" + "A" * 400
IMAGE_REPLY = {"created": 1, "data": [{"b64_json": IMAGE_B64}]}


def image_request(model, text):
	return ImageRequest(model=model, prompt=text, response_format="b64_json")


AUDIO_BYTES = b"RIFF-not-really-audio" * 20
TRANSCRIPT_REPLY = {"text": "hello from the meeting"}


def transcription_request(model, text):
	return TranscriptionRequest(model=model, filename="meeting.mp3", data=AUDIO_BYTES, prompt=text)


def speech_request(model, text):
	return SpeechRequest(model=model, input=text, voice="alloy", response_format="wav")


RESPONSES_REPLY = {
	"id": "resp_1", "object": "response",
	"output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Here is the summary."}]}],
	"usage": {"input_tokens": 12, "output_tokens": 5},
}


def responses_request(model, text):
	return ResponsesRequest(model=model, input=text)


class SpeechReply:
	content = b"RIFFfake-wav-bytes"


# id, modality (or a function of the request, for speech), request factory, provider function, provider reply, model, the registry class that clears it.
# Audio cannot be inspected, so a transcription is classified as uninspected (confidential) and needs a model cleared for that.
CASES = [
	("rerank", RERANK, rerank_request, "arerank", RERANK_REPLY, "cohere/rerank-english-v3.0", "internal"),
	("image", IMAGES, image_request, "aimage_generation", IMAGE_REPLY, "openai/dall-e-3", "internal"),
	("transcription", TRANSCRIPTION, transcription_request, "atranscription", TRANSCRIPT_REPLY, "openai/whisper-1", "confidential"),
	("speech", speech_modality, speech_request, "aspeech", SpeechReply(), "openai/tts-1", "internal"),
	("responses", RESPONSES, responses_request, "aresponses", RESPONSES_REPLY, "openai/gpt-4o", "internal"),
]


@pytest.fixture(params=CASES, ids=lambda c: c[0])
def case(request, monkeypatch):
	name, modality, make, fn, reply, model, level = request.param
	seen = SimpleNamespace(calls=[], key_requests=[], limit_checks=[], policy=PolicyConfig(), registry=[], limited=False, error=None, reply=reply)

	async def provider(**kwargs):
		seen.calls.append(kwargs)
		if seen.error:
			raise seen.error
		return seen.reply

	async def select_keys(db, org_id, provider_name, model=None, redis=None, max_attempts=None, only_key_id=None):
		seen.key_requests.append(only_key_id)
		return [ProviderKeyCandidate(KEY, "sk-test", None)]

	async def load(org_id, db, redis):
		return seen.policy

	async def routing_inputs(db, org_id):
		return list(seen.registry), "us"

	async def check_limits(**kwargs):
		seen.limit_checks.append(kwargs)
		return (False, {}, "rpm", "slow down", 3) if seen.limited else (True, {}, None, None, None)

	monkeypatch.setattr(llm_module, fn, provider)
	monkeypatch.setattr(llm_module.settings, "DEBUG", False)
	monkeypatch.setattr(llm_service, "_select_provider_keys", select_keys)
	monkeypatch.setattr(llm_service, "routing_inputs", routing_inputs)
	monkeypatch.setattr(policy_store, "load", load)
	monkeypatch.setattr(rate_limiter.rate_limiter_service, "check_limits", check_limits)
	monkeypatch.setattr(llm_module.cost_tracker_service, "calculate_cost_usd", lambda _r, call_type=None: Decimal("0.001"))
	seen.name, seen.modality, seen.make, seen.model, seen.level = name, modality, make, model, level
	return seen


async def send(case, *, text="the answer", model=None, headers=None):
	logged = []

	async def fake_log(**kwargs):
		logged.append(kwargs)

	tasks, original = BackgroundTasks(), llm_module.log_request
	llm_module.log_request = fake_log
	user, api_key = SimpleNamespace(id=USER, org_id=ORG, budget_daily_usd=None), SimpleNamespace(id=uuid.uuid4(), team_id=None)
	try:
		try:
			request = case.make(model or case.model, text)
			modality = case.modality(request) if callable(case.modality) else case.modality
			result = await run_modality(
				modality, request, db=MagicMock(), redis=MagicMock(), user=user, api_key=api_key, request_id=uuid.uuid4(),
				background_tasks=tasks, http_request=SimpleNamespace(headers=headers or {}, state=SimpleNamespace(), client=SimpleNamespace(host="1.2.3.4")),
			)
		except HTTPException as exc:
			result = exc
		for task in tasks.tasks:
			await fake_log(**task.kwargs)
		if llm_module._DETACHED_TASKS:
			await asyncio.gather(*list(llm_module._DETACHED_TASKS), return_exceptions=True)
	finally:
		llm_module.log_request = original
	return result, logged


async def test_a_successful_call_reaches_the_provider_with_the_key_and_is_audited(case):
	response, logged = await send(case)
	assert response.status_code == 200 and response.headers["x-openproxyai-model"] == case.model
	assert case.calls[0]["api_key"] == "sk-test" and case.calls[0]["model"] == case.model
	assert [row["status_code"] for row in logged] == [200] and logged[0]["provider_key_id"] == KEY and logged[0]["prompt_tokens"] > 0


async def test_a_policy_block_is_a_446_and_the_provider_never_sees_the_text(case):
	case.policy = PolicyConfig(enforcement_mode="enforce", blocked_keywords=["forbidden"])
	response, logged = await send(case, text="this is forbidden")
	assert response.status_code == 446 and case.calls == [] and [row["status_code"] for row in logged] == [446]


async def test_every_part_of_the_request_is_scanned_not_just_the_first_field(case):
	"""A marker in a later field (a document, not the query) is found: the whole request is one text to policy."""
	case.policy = PolicyConfig(enforcement_mode="enforce", blocked_keywords=["hidden-marker"])
	response, _ = await send(case, text="a document carrying hidden-marker")
	assert response.status_code == 446 and case.calls == []


async def test_pii_anywhere_in_the_request_raises_its_class(case):
	response, logged = await send(case, text="ssn 123-45-6789")
	assert response.headers["x-openproxyai-data-class"] == "confidential" and logged[0]["request_metadata"]["data_class"]["entities"]


async def test_enforced_routing_refuses_an_unregistered_model_and_a_model_not_cleared_for_the_data_class(case):
	case.policy = PolicyConfig(routing_mode="enforce")
	response, _ = await send(case)
	assert response.status_code == 446 and json.loads(response.body)["route_reason"] == "not_in_registry" and case.calls == []
	case.registry = [entry(case.model, level=case.level)]
	response, _ = await send(case, headers={"x-openproxy-data-class": "secret"})
	assert response.status_code == 446 and case.calls == []
	response, _ = await send(case)
	assert response.status_code == 200 and case.key_requests[-1] == case.registry[0].key_id  # served through its registry key only


async def test_rate_limits_apply_and_are_sized_from_the_request(case):
	case.limited = True
	response, logged = await send(case)
	assert response.status_code == 429 and case.calls == [] and [row["status_code"] for row in logged] == [429]
	assert case.limit_checks[0]["request_tokens_estimate"] >= 1


async def test_a_provider_failure_is_a_502_that_does_not_echo_provider_text(case):
	case.error = RuntimeError("boom sk-secret")
	failure, logged = await send(case)
	assert isinstance(failure, HTTPException) and failure.status_code == 502 and "sk-secret" not in json.dumps(failure.detail)
	assert [row["status_code"] for row in logged] == [502]


async def test_a_model_litellm_cannot_price_still_returns_its_answer_and_is_charged_a_flat_fallback_never_zero(case, monkeypatch):
	def unpriced(_response, call_type=None):
		raise ValueError("model not in the price map")

	monkeypatch.setattr(llm_module.cost_tracker_service, "calculate_cost_usd", unpriced)
	monkeypatch.setattr(llm_module.settings, "UNPRICED_CALL_COST_USD", 0.02)
	response, logged = await send(case)
	assert response.status_code == 200 and logged[0]["status_code"] == 200
	built = case.make(case.model, "the answer")
	expected = Decimal("0.02") * (case.modality(built) if callable(case.modality) else case.modality).units(built)
	assert logged[0]["cost_usd"] == expected and expected > 0 and logged[0]["request_metadata"]["cost_estimated"] is True


async def test_each_modality_prices_its_call_as_what_it_is(case, monkeypatch):
	seen = []

	def record(_response, call_type=None):
		seen.append(call_type)
		return Decimal("0.001")

	monkeypatch.setattr(llm_module.cost_tracker_service, "calculate_cost_usd", record)
	await send(case)
	built = case.make(case.model, "the answer")
	modality = case.modality(built) if callable(case.modality) else case.modality
	assert seen == [modality.call_type] and modality.call_type is not None


# -- rerank specifics ------------------------------------------------------------------------------


async def test_rerank_sends_the_query_and_documents_as_given_and_returns_the_ranking(case):
	if case.name != "rerank":
		pytest.skip("rerank only")
	request = RerankRequest(model=case.model, query="q", documents=["a", {"text": "b"}], top_n=1, return_documents=False)
	response = await run_modality(
		RERANK, request, db=MagicMock(), redis=MagicMock(), user=SimpleNamespace(id=USER, org_id=ORG, budget_daily_usd=None),
		api_key=SimpleNamespace(id=uuid.uuid4(), team_id=None), request_id=uuid.uuid4(), background_tasks=BackgroundTasks(),
		http_request=SimpleNamespace(headers={}, state=SimpleNamespace(), client=SimpleNamespace(host="x")),
	)
	assert json.loads(response.body)["results"][0]["index"] == 1
	call = case.calls[0]
	assert (call["query"], call["documents"], call["top_n"], call["return_documents"]) == ("q", ["a", "b"], 1, False)


@pytest.mark.parametrize("body", [
	{"query": "q", "documents": []}, {"query": "", "documents": ["a"]}, {"query": "q", "documents": ["a"], "top_n": 0},
	{"query": "q", "documents": [{"nope": "x"}]}, {"query": "q", "documents": ["x" * 50_001]}, {"query": "q", "documents": ["a"] * 1_001},
	{"query": "q", "documents": ["a"], "surprise": 1}, {"query": "x" * 10_001, "documents": ["a"]},
])
def test_rerank_rejects_malformed_or_oversized_requests(body):
	with pytest.raises(ValueError):
		RerankRequest(model="cohere/rerank-english-v3.0", **body)


def test_rerank_accepts_documents_as_text_objects_and_reads_them_as_text():
	request = RerankRequest(model="cohere/x", query="q", documents=["plain", {"text": "wrapped"}])
	assert request.texts() == ["plain", "wrapped"]


# -- images specifics --------------------------------------------------------------------------------


async def test_a_generated_image_is_returned_but_never_written_to_the_audit_log(case):
	if case.name != "image":
		pytest.skip("images only")
	response, logged = await send(case)
	assert json.loads(response.body)["data"][0]["b64_json"] == IMAGE_B64
	assert IMAGE_B64[:40] not in json.dumps(logged, default=str)


async def test_an_image_counts_heavily_toward_the_token_rate_limit(case):
	if case.name != "image":
		pytest.skip("images only")
	await send(case)
	assert case.limit_checks[0]["request_tokens_estimate"] >= 1_000


async def test_image_options_reach_the_provider_only_when_set(case):
	if case.name != "image":
		pytest.skip("images only")
	await send(case)
	sent = case.calls[0]
	assert (sent["n"], sent["response_format"]) == (1, "b64_json") and "size" not in sent and "style" not in sent


@pytest.mark.parametrize("body", [
	{"prompt": ""}, {"prompt": "x" * 4_001}, {"prompt": "a", "n": 5}, {"prompt": "a", "n": 0}, {"prompt": "a", "size": "99999x99999"},
	{"prompt": "a", "response_format": "file"}, {"prompt": "a", "surprise": 1},
])
def test_image_requests_outside_the_limits_are_rejected(body):
	with pytest.raises(ValueError):
		ImageRequest(model="openai/dall-e-3", **body)


# -- audio specifics ---------------------------------------------------------------------------------


async def test_audio_cannot_be_inspected_so_a_transcription_is_classified_as_uninspected(case):
	if case.name != "transcription":
		pytest.skip("transcription only")
	response, logged = await send(case, text="a harmless hint")
	assert response.headers["x-openproxyai-data-class"] == "confidential"
	assert "__unscanned__" in logged[0]["request_metadata"]["data_class"]["entities"]


async def test_a_transcription_model_cleared_only_for_internal_data_never_receives_the_audio(case):
	if case.name != "transcription":
		pytest.skip("transcription only")
	case.policy = PolicyConfig(routing_mode="enforce")
	case.registry = [entry(case.model, level="internal")]
	response, _ = await send(case)
	assert response.status_code == 446 and case.calls == []


async def test_the_audio_reaches_the_provider_as_a_named_file_and_the_hint_is_scanned(case):
	if case.name != "transcription":
		pytest.skip("transcription only")
	await send(case, text="names: Alice")
	sent = case.calls[0]
	assert sent["file"].name == "meeting.mp3" and sent["file"].read() == AUDIO_BYTES and sent["prompt"] == "names: Alice"


async def test_a_transcript_goes_through_the_orgs_response_guardrails(case):
	if case.name != "transcription":
		pytest.skip("transcription only")
	case.policy = PolicyConfig(enforcement_mode="enforce", response_guardrails_enabled=True, blocked_keywords=["meeting"])
	response, logged = await send(case)
	assert isinstance(response, HTTPException) and response.status_code == 446
	assert response.detail["error"]["code"] == "response_policy_violation" and logged[0]["status_code"] == 446


async def test_a_transcript_with_pii_is_redacted_when_the_org_asked_for_redaction(case):
	if case.name != "transcription":
		pytest.skip("transcription only")
	case.reply = {"text": "call me on 123-45-6789 please"}
	case.policy = PolicyConfig(response_guardrails_enabled=True, response_pii_redact=True)
	response, _ = await send(case)
	assert "123-45-6789" not in json.loads(response.body)["text"] and "[REDACTED" in json.loads(response.body)["text"]


async def test_speech_comes_back_as_audio_bytes_with_the_right_type(case):
	if case.name != "speech":
		pytest.skip("speech only")
	response, logged = await send(case)
	assert response.body == SpeechReply.content and response.media_type == "audio/wav"
	assert response.headers["x-openproxyai-request-id"] and logged[0]["status_code"] == 200
	assert case.calls[0]["voice"] == "alloy" and case.calls[0]["response_format"] == "wav" and "speed" not in case.calls[0]


async def test_a_provider_that_returns_no_audio_is_a_502_not_an_empty_200(case):
	if case.name != "speech":
		pytest.skip("speech only")
	case.reply = object()
	failure, _ = await send(case)
	assert isinstance(failure, HTTPException) and failure.status_code == 502


@pytest.mark.parametrize("body", [
	{"input": ""}, {"input": "x" * 4_097}, {"input": "hi", "voice": "bad voice!"}, {"input": "hi", "voice": ""},
	{"input": "hi", "response_format": "exe"}, {"input": "hi", "speed": 9}, {"input": "hi", "speed": 0.1}, {"input": "hi", "surprise": 1},
])
def test_speech_requests_outside_the_limits_are_rejected(body):
	with pytest.raises(ValueError):
		SpeechRequest(**{"model": "openai/tts-1", "voice": "alloy", **body})


@pytest.mark.parametrize("fields", [
	{"filename": "notes.txt"}, {"filename": "noextension"}, {"filename": "evil.exe"}, {"data": b""}, {"language": "english"},
	{"temperature": 2}, {"prompt": "x" * 1_001}, {"response_format": "xml"},
])
def test_transcription_requests_outside_the_limits_are_rejected(fields):
	with pytest.raises(ValueError):
		TranscriptionRequest(**{"model": "openai/whisper-1", "filename": "a.mp3", "data": b"x", **fields})


# -- responses specifics -----------------------------------------------------------------------------


async def test_store_is_always_sent_explicitly_as_false_so_the_provider_keeps_nothing_by_default(case):
	if case.name != "responses":
		pytest.skip("responses only")
	await send(case)
	assert case.calls[0]["store"] is False and "previous_response_id" not in case.calls[0]


@pytest.mark.parametrize("fields", [{"store": True}, {"previous_response_id": "resp_123"}])
async def test_provider_side_state_is_refused_unless_the_org_allows_it(case, fields):
	if case.name != "responses":
		pytest.skip("responses only")
	original = case.make

	case.make = lambda model, text: ResponsesRequest(model=model, input=text, **fields)
	failure, logged = await send(case)
	assert isinstance(failure, HTTPException) and failure.status_code == 400 and failure.detail["error"] == "provider_state_not_allowed"
	assert case.calls == [] and [row["status_code"] for row in logged] == [400]

	case.policy = PolicyConfig(allow_provider_response_state=True)
	response, _ = await send(case)
	assert response.status_code == 200 and case.calls[0]["store"] is bool(fields.get("store"))
	case.make = original


async def test_the_whole_structured_input_is_scanned_including_tool_definitions_and_instructions(case):
	if case.name != "responses":
		pytest.skip("responses only")
	case.policy = PolicyConfig(enforcement_mode="enforce", blocked_keywords=["hidden-marker"])
	for fields in (
		{"instructions": "be nice, hidden-marker"},
		{"tools": [{"type": "function", "name": "lookup", "description": "uses hidden-marker", "parameters": {}}]},
		{"input": [{"role": "user", "content": [{"type": "input_text", "text": "carrying hidden-marker"}]}]},
	):
		case.make = lambda model, text, fields=fields: ResponsesRequest(**{"model": model, "input": text, **fields})
		response, _ = await send(case)
		assert response.status_code == 446, fields
	assert case.calls == []


async def test_an_image_input_is_uninspected_so_a_model_cleared_only_for_internal_data_never_receives_it(case):
	if case.name != "responses":
		pytest.skip("responses only")
	case.make = lambda model, text: ResponsesRequest(
		model=model, input=[{"role": "user", "content": [{"type": "input_image", "image_url": "data:image/png;base64,AAAA"}]}]
	)
	case.policy = PolicyConfig(routing_mode="enforce")
	case.registry = [entry(case.model, level="internal")]
	response, _ = await send(case)
	assert response.status_code == 446 and case.calls == []


async def test_a_text_only_input_is_not_treated_as_uninspected(case):
	if case.name != "responses":
		pytest.skip("responses only")
	response, _ = await send(case)
	assert response.headers["x-openproxyai-data-class"] == "internal"


async def test_the_answer_text_goes_through_response_guardrails(case):
	if case.name != "responses":
		pytest.skip("responses only")
	case.policy = PolicyConfig(enforcement_mode="enforce", response_guardrails_enabled=True, blocked_keywords=["summary"])
	failure, _ = await send(case)
	assert isinstance(failure, HTTPException) and failure.status_code == 446
	case.policy = PolicyConfig(response_guardrails_enabled=True, response_pii_redact=True)
	case.reply = {**RESPONSES_REPLY, "output": [{"type": "message", "content": [{"type": "output_text", "text": "ssn 123-45-6789"}, {"type": "output_text", "text": "and 078-05-1120"}]}]}
	response, _ = await send(case)
	text = json.dumps(json.loads(response.body))
	assert "123-45-6789" not in text and "078-05-1120" not in text


async def test_token_usage_is_read_from_the_responses_shape(case):
	if case.name != "responses":
		pytest.skip("responses only")
	_, logged = await send(case)
	assert (logged[0]["prompt_tokens"], logged[0]["completion_tokens"]) == (12, 5)


@pytest.mark.parametrize("body", [
	{"input": ""}, {"input": []}, {"input": "hi", "stream": True}, {"input": "hi", "background": True}, {"input": "hi", "conversation": "c1"},
	{"input": "hi", "tools": [{"type": "web_search"}]}, {"input": "hi", "tools": [{"type": "code_interpreter"}]},
	{"input": "hi", "tools": [{"type": "mcp", "server_url": "https://evil.example"}]}, {"input": "hi", "tools": [{"type": "file_search"}]},
	{"input": "hi", "temperature": 3}, {"input": "hi", "max_output_tokens": 0}, {"input": "hi", "surprise": 1},
	{"input": [{"role": "user", "content": "x"}] * 501},
])
def test_responses_requests_that_could_run_things_at_the_provider_or_are_malformed_are_rejected(body):
	with pytest.raises(ValueError):
		ResponsesRequest(model="openai/gpt-4o", **body)


def test_client_side_function_tools_are_accepted():
	request = ResponsesRequest(model="openai/gpt-4o", input="hi", tools=[{"type": "function", "name": "lookup", "parameters": {}}])
	assert request.tools[0]["name"] == "lookup"


async def test_a_request_too_large_to_scan_is_refused_not_scanned_in_part(case):
	if case.name != "responses":
		pytest.skip("responses only")
	huge = {f"key{i}": i for i in range(60_000)}  # more nodes than the scanner will walk
	case.make = lambda model, text: ResponsesRequest(model=model, input=text, tools=[{"type": "function", "name": "f", "parameters": huge}])
	response, logged = await send(case)
	assert response.status_code == 446 and json.loads(response.body)["reason_code"] == "scan_limit_exceeded"
	assert case.calls == [] and logged[0]["error_message"] == "policy_blocked:scan_limit_exceeded"


# -- found by the security review: what is read, referenced and delivered -----------------------------


def _responses_case(case, **fields):
	if case.name != "responses":
		pytest.skip("responses only")
	case.make = lambda model, text: ResponsesRequest(**{"model": model, "input": text, **fields})


@pytest.mark.parametrize("item", [
	{"type": "item_reference", "id": "msg_stored"},
	{"role": "user", "content": [{"type": "input_text", "text": "see file"}, {"type": "input_file", "file_id": "file-abc"}]},
	{"role": "user", "content": "hi", "attachments": [{"file_id": "file-abc"}]},
])
async def test_input_that_points_at_state_the_provider_holds_is_refused_unless_the_org_allows_it(case, item):
	_responses_case(case, input=[item])
	failure, _ = await send(case)
	assert isinstance(failure, HTTPException) and failure.detail["error"] == "provider_state_not_allowed" and case.calls == []
	case.policy = PolicyConfig(allow_provider_response_state=True)
	response, _ = await send(case)
	assert response.status_code == 200


@pytest.mark.parametrize("item", [
	{"role": "user", "content": [{"type": "input_image", "image_url": "data:image/png;base64,AAAA"}]},
	{"role": "user", "content": "hi", "extras": {"nested": [{"image_url": "https://example.com/x.png"}]}},  # hidden outside `content`
	{"role": "user", "content": [{"type": "brand_new_part", "payload": "???"}]},  # a type that does not exist yet: not assumed harmless
	{"type": "reasoning", "encrypted_content": "gAAAA", "summary": []},
])
async def test_any_input_the_gateway_cannot_read_or_does_not_recognise_is_uninspected_wherever_it_hides(case, item):
	_responses_case(case, input=[item])
	case.policy = PolicyConfig(routing_mode="enforce")
	case.registry = [entry(case.model, level="internal")]
	response, _ = await send(case, headers={"x-openproxy-data-class": "internal"})
	assert response.status_code == 446 and case.calls == []


async def test_plain_text_items_in_their_known_shapes_stay_inspected(case):
	_responses_case(case, input=[
		{"role": "user", "content": [{"type": "input_text", "text": "hello"}]},
		{"type": "function_call", "call_id": "c1", "name": "lookup", "arguments": "{}"},
		{"type": "function_call_output", "call_id": "c1", "output": "42"},
	])
	response, _ = await send(case)
	assert response.status_code == 200 and response.headers["x-openproxyai-data-class"] == "internal"


@pytest.mark.parametrize("output", [
	[{"type": "function_call", "call_id": "c", "name": "send", "arguments": '{"to": "x", "body": "the summary of the hidden-marker plan"}'}],
	[{"type": "message", "content": [{"type": "refusal", "refusal": "I cannot share the hidden-marker plan"}]}],
	[{"type": "reasoning", "summary": [{"type": "summary_text", "text": "thinking about the hidden-marker plan"}]}],
])
async def test_every_string_the_model_produced_is_checked_not_only_the_message_text(case, output):
	if case.name != "responses":
		pytest.skip("responses only")
	case.reply = {**RESPONSES_REPLY, "output": output}
	case.policy = PolicyConfig(enforcement_mode="enforce", response_guardrails_enabled=True, blocked_keywords=["hidden-marker"])
	failure, _ = await send(case)
	assert isinstance(failure, HTTPException) and failure.status_code == 446


async def test_pii_is_redacted_in_function_call_arguments_and_refusals_too(case):
	if case.name != "responses":
		pytest.skip("responses only")
	case.reply = {**RESPONSES_REPLY, "output": [
		{"type": "function_call", "call_id": "c", "name": "send", "arguments": '{"ssn": "123-45-6789"}'},
		{"type": "message", "content": [{"type": "refusal", "refusal": "not for 078-05-1120"}]},
	]}
	case.policy = PolicyConfig(response_guardrails_enabled=True, response_pii_redact=True)
	response, _ = await send(case)
	text = response.body.decode()
	assert "123-45-6789" not in text and "078-05-1120" not in text and '"name":"send"' in text  # structure is left alone


async def test_a_verbose_transcript_is_redacted_in_its_segments_and_words_not_only_its_headline_text(case):
	if case.name != "transcription":
		pytest.skip("transcription only")
	case.reply = {
		"text": "my number is 123-45-6789", "language": "en", "duration": 3.1,
		"segments": [{"id": 0, "text": "my number is 123-45-6789", "start": 0, "end": 2}],
		"words": [{"word": "123-45-6789", "start": 1, "end": 2}],
	}
	case.policy = PolicyConfig(response_guardrails_enabled=True, response_pii_redact=True)
	response, _ = await send(case)
	body = json.loads(response.body)
	assert "123-45-6789" not in response.body.decode() and body["language"] == "en" and body["segments"][0]["start"] == 0


async def test_a_blocked_keyword_only_in_a_segment_still_blocks_the_transcript(case):
	if case.name != "transcription":
		pytest.skip("transcription only")
	case.reply = {"text": "all fine", "segments": [{"id": 0, "text": "the hidden-marker plan"}]}
	case.policy = PolicyConfig(enforcement_mode="enforce", response_guardrails_enabled=True, blocked_keywords=["hidden-marker"])
	failure, _ = await send(case)
	assert isinstance(failure, HTTPException) and failure.status_code == 446
