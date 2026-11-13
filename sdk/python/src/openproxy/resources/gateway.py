"""Gateway endpoints beyond chat and embeddings: models, rerank, images, audio, Responses, feedback, files, batches.

Every method is a thin wrapper over one HTTP call; the gateway applies the same policy, routing and audit to all of them.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Union

if TYPE_CHECKING:
    from .._async_client import AsyncOpenProxy
    from .._client import OpenProxy

# bytes, or (filename, bytes)
FileInput = Union[bytes, "tuple[str, bytes]"]


def _file_part(file: FileInput, default_name: str) -> tuple[str, bytes]:
    if isinstance(file, tuple):
        return file
    return (default_name, file)


def _clean(**fields: Any) -> dict:
    return {k: v for k, v in fields.items() if v is not None}


class _SyncBase:
    def __init__(self, client: "OpenProxy"):
        self._client = client

    def _json(self, method: str, path: str, **kwargs) -> Any:
        return self._client._request(method, path, **kwargs).json()


class _AsyncBase:
    def __init__(self, client: "AsyncOpenProxy"):
        self._client = client

    async def _json(self, method: str, path: str, **kwargs) -> Any:
        return (await self._client._request(method, path, **kwargs)).json()


class SyncModelsResource(_SyncBase):
    def list(self) -> dict:
        return self._json("GET", "/v1/models")


class AsyncModelsResource(_AsyncBase):
    async def list(self) -> dict:
        return await self._json("GET", "/v1/models")


class SyncRerankResource(_SyncBase):
    def create(self, model: str, query: str, documents: list, top_n: int | None = None, return_documents: bool = True) -> dict:
        body = _clean(model=model, query=query, documents=documents, top_n=top_n, return_documents=return_documents)
        return self._json("POST", "/v1/rerank", json=body)


class AsyncRerankResource(_AsyncBase):
    async def create(self, model: str, query: str, documents: list, top_n: int | None = None, return_documents: bool = True) -> dict:
        body = _clean(model=model, query=query, documents=documents, top_n=top_n, return_documents=return_documents)
        return await self._json("POST", "/v1/rerank", json=body)


class SyncImagesResource(_SyncBase):
    def generate(self, model: str, prompt: str, **options) -> dict:
        return self._json("POST", "/v1/images/generations", json={"model": model, "prompt": prompt, **options})


class AsyncImagesResource(_AsyncBase):
    async def generate(self, model: str, prompt: str, **options) -> dict:
        return await self._json("POST", "/v1/images/generations", json={"model": model, "prompt": prompt, **options})


class SyncAudioResource(_SyncBase):
    def speech(self, model: str, input: str, voice: str, **options) -> bytes:
        """Text to speech. Returns the audio bytes."""
        body = {"model": model, "input": input, "voice": voice, **options}
        return self._client._request("POST", "/v1/audio/speech", json=body).content

    def transcribe(self, model: str, file: FileInput, **fields: str) -> dict:
        """Speech to text. ``file`` is audio bytes or ``(filename, bytes)``. Extra form fields (language, prompt) pass through."""
        files = {"file": _file_part(file, "audio")}
        return self._json("POST", "/v1/audio/transcriptions", data={"model": model, **fields}, files=files)


class AsyncAudioResource(_AsyncBase):
    async def speech(self, model: str, input: str, voice: str, **options) -> bytes:
        body = {"model": model, "input": input, "voice": voice, **options}
        return (await self._client._request("POST", "/v1/audio/speech", json=body)).content

    async def transcribe(self, model: str, file: FileInput, **fields: str) -> dict:
        files = {"file": _file_part(file, "audio")}
        return await self._json("POST", "/v1/audio/transcriptions", data={"model": model, **fields}, files=files)


class SyncResponsesResource(_SyncBase):
    def create(self, model: str, input: Any, **options) -> dict:
        return self._json("POST", "/v1/responses", json={"model": model, "input": input, **options})


class AsyncResponsesResource(_AsyncBase):
    async def create(self, model: str, input: Any, **options) -> dict:
        return await self._json("POST", "/v1/responses", json={"model": model, "input": input, **options})


def _feedback_body(request_id: str, thumbs: str | None, value: float | None, score_name: str | None, comment: str | None) -> dict:
    return _clean(request_id=request_id, thumbs=thumbs, value=value, score_name=score_name, comment=comment)


class SyncFeedbackResource(_SyncBase):
    def create(self, request_id: str, thumbs: str | None = None, value: float | None = None, score_name: str | None = None, comment: str | None = None) -> dict:
        """Rate an answer. ``request_id`` is the ``x-openproxyai-request-id`` response header. Send exactly one of ``thumbs`` or ``value``."""
        return self._json("POST", "/v1/feedback", json=_feedback_body(request_id, thumbs, value, score_name, comment))


class AsyncFeedbackResource(_AsyncBase):
    async def create(self, request_id: str, thumbs: str | None = None, value: float | None = None, score_name: str | None = None, comment: str | None = None) -> dict:
        return await self._json("POST", "/v1/feedback", json=_feedback_body(request_id, thumbs, value, score_name, comment))


class SyncFilesResource(_SyncBase):
    def create(self, file: FileInput, purpose: str = "batch") -> dict:
        """Upload a JSONL file of chat requests for a batch."""
        return self._json("POST", "/v1/files", data={"purpose": purpose}, files={"file": _file_part(file, "batch.jsonl")})

    def retrieve(self, file_id: str) -> dict:
        return self._json("GET", f"/v1/files/{file_id}")

    def content(self, file_id: str) -> bytes:
        return self._client._request("GET", f"/v1/files/{file_id}/content").content

    def delete(self, file_id: str) -> dict:
        return self._json("DELETE", f"/v1/files/{file_id}")


class AsyncFilesResource(_AsyncBase):
    async def create(self, file: FileInput, purpose: str = "batch") -> dict:
        return await self._json("POST", "/v1/files", data={"purpose": purpose}, files={"file": _file_part(file, "batch.jsonl")})

    async def retrieve(self, file_id: str) -> dict:
        return await self._json("GET", f"/v1/files/{file_id}")

    async def content(self, file_id: str) -> bytes:
        return (await self._client._request("GET", f"/v1/files/{file_id}/content")).content

    async def delete(self, file_id: str) -> dict:
        return await self._json("DELETE", f"/v1/files/{file_id}")


def _batch_body(input_file_id: str, max_cost_usd: float | None, metadata: dict[str, str] | None) -> dict:
    return _clean(input_file_id=input_file_id, max_cost_usd=max_cost_usd, metadata=metadata)


class SyncBatchesResource(_SyncBase):
    def create(self, input_file_id: str, max_cost_usd: float | None = None, metadata: dict[str, str] | None = None) -> dict:
        """Run an uploaded file as one governed job. ``max_cost_usd`` caps the spend."""
        return self._json("POST", "/v1/batches", json=_batch_body(input_file_id, max_cost_usd, metadata))

    def retrieve(self, batch_id: str) -> dict:
        return self._json("GET", f"/v1/batches/{batch_id}")

    def list(self, limit: int = 20) -> dict:
        return self._json("GET", "/v1/batches", params={"limit": limit})

    def cancel(self, batch_id: str) -> dict:
        return self._json("POST", f"/v1/batches/{batch_id}/cancel")


class AsyncBatchesResource(_AsyncBase):
    async def create(self, input_file_id: str, max_cost_usd: float | None = None, metadata: dict[str, str] | None = None) -> dict:
        return await self._json("POST", "/v1/batches", json=_batch_body(input_file_id, max_cost_usd, metadata))

    async def retrieve(self, batch_id: str) -> dict:
        return await self._json("GET", f"/v1/batches/{batch_id}")

    async def list(self, limit: int = 20) -> dict:
        return await self._json("GET", "/v1/batches", params={"limit": limit})

    async def cancel(self, batch_id: str) -> dict:
        return await self._json("POST", f"/v1/batches/{batch_id}/cancel")
