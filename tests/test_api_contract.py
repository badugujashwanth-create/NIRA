from __future__ import annotations

from fastapi.testclient import TestClient

from nira_core.api import create_app


def test_health_and_models_endpoints() -> None:
    app = create_app()
    client = TestClient(app)
    health = client.get("/health")
    models = client.get("/models")
    state = client.get("/state")
    capabilities = client.get("/capabilities")
    reflection = client.get("/reflection")
    recommendation = client.post(
        "/capabilities/recommend",
        json={"goal": "retrieve context and read project files", "permissions": ["filesystem"]},
    )
    assert health.status_code == 200
    assert health.json()["ok"] is True
    assert models.status_code == 200
    assert models.json()["models"]
    assert state.status_code == 200
    assert "queue_depth" in state.json()
    assert capabilities.status_code == 200
    assert capabilities.json()["capabilities"]
    assert reflection.status_code == 200
    assert "latency_mode" in reflection.json()
    assert recommendation.status_code == 200
    assert recommendation.json()["capabilities"]
