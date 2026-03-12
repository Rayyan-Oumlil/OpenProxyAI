"""Health check endpoint tests."""


def test_health_returns_200(client):
	response = client.get("/health")
	assert response.status_code == 200
	data = response.json()
	assert data["status"] == "healthy"
	assert data["app"] == "OpenProxyAI"
	assert data["version"] == "0.1.0"


def test_health_response_has_request_id_header(client):
	response = client.get("/health")
	assert "x-openproxyai-request-id" in response.headers
	assert response.headers["x-openproxyai-request-id"]


def test_health_response_has_latency_header(client):
	response = client.get("/health")
	assert "x-openproxyai-latency-ms" in response.headers
	latency = int(response.headers["x-openproxyai-latency-ms"])
	assert latency >= 0
