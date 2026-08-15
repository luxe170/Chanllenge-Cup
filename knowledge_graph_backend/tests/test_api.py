from datetime import date

from fastapi.testclient import TestClient

from app.catalog import load_catalog
from app.domain import AggregatedRequirement, RequirementType, Trend
from app.graph import build_projection
from app.main import app
from app.runtime import get_graph_repository


def seed_graph():
    repository = get_graph_repository()
    repository.publish(
        build_projection(
            load_catalog(),
            [
                AggregatedRequirement(
                    "pos_ai_agent_engineer",
                    "skill_rag",
                    RequirementType.REQUIRED,
                    0.9,
                    0.8,
                    0.92,
                    8,
                    ["jd_1"],
                    date(2026, 7, 1),
                    date(2026, 8, 1),
                    Trend.RISING,
                )
            ],
            "graph_api_test",
        )
    )


def test_health_and_graph_contracts():
    with TestClient(app) as client:
        seed_graph()
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["data"]["status"] == "ok"
        canonical = client.get("/api/v1/graph", params={"mode": "panorama"})
        assert canonical.status_code == 200
        assert "position_category" in canonical.json()["data"]["hierarchy"]
        compatible = client.get("/api/v1/graph", params={"mode": "panorama", "contract": "frontend_v1"})
        assert "cluster" in compatible.json()["data"]["hierarchy"]
        assert all(node["type"] != "position_category" for node in compatible.json()["data"]["nodes"])


def test_admin_endpoint_requires_key():
    with TestClient(app) as client:
        response = client.post("/api/v1/entities", json={"id": "skill_demo", "entityType": "skill", "name": "Demo", "properties": {"skill_type": "tool", "cluster_id": "cluster_software_engineering"}})
        assert response.status_code == 401

