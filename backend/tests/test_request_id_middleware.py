"""The request id header must appear once: clients copy it into POST /v1/feedback, which wants a single UUID."""

from __future__ import annotations

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.middleware.request_id import RequestIdMiddleware

ROUTE_ID = "11111111-1111-4111-8111-111111111111"


def build() -> FastAPI:
	app = FastAPI()
	app.add_middleware(RequestIdMiddleware)

	@app.get("/sets-its-own")
	async def sets_its_own():
		return JSONResponse({}, headers={"X-OpenProxyAI-Request-Id": ROUTE_ID})

	@app.get("/sets-nothing")
	async def sets_nothing():
		return JSONResponse({})

	return app


async def get(path: str) -> httpx.Response:
	async with httpx.AsyncClient(transport=httpx.ASGITransport(app=build()), base_url="http://t") as client:
		return await client.get(path)


async def test_a_route_that_sets_the_header_keeps_its_value_and_the_header_is_not_duplicated():
	response = await get("/sets-its-own")
	assert response.headers.get_list("x-openproxyai-request-id") == [ROUTE_ID]


async def test_a_response_without_one_gets_the_middlewares_id():
	[value] = (await get("/sets-nothing")).headers.get_list("x-openproxyai-request-id")
	assert len(value) == 32 and value.isalnum()
