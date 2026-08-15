from datetime import date

from app.catalog import load_catalog
from app.domain import AggregatedRequirement, RequirementType, Trend
from app.graph import InMemoryGraphRepository, build_projection


def projection():
    requirement = AggregatedRequirement(
        position_id="pos_ai_agent_engineer",
        skill_id="skill_rag",
        requirement_type=RequirementType.REQUIRED,
        weight=0.88,
        frequency=0.75,
        confidence=0.91,
        sample_count=6,
        source_ids=["jd_1", "jd_2"],
        first_seen=date(2026, 7, 1),
        last_seen=date(2026, 8, 1),
        trend=Trend.RISING,
    )
    return build_projection(load_catalog(), [requirement], "graph_test")


def test_projection_contains_explicit_category_and_skill_hierarchy():
    graph = projection()
    types = {node.type.value for node in graph.nodes}
    relationships = {edge.relationship.value for edge in graph.edges}
    assert {"position", "position_category", "skill", "skill_cluster", "tech_stack"} <= types
    assert {"IN_CATEGORY", "REQUIRES", "BELONGS_TO"} <= relationships


def test_repository_subgraph_has_no_dangling_edges():
    repository = InMemoryGraphRepository()
    repository.publish(projection())
    data = repository.graph("skill_reverse", max_nodes=3)
    ids = {node["id"] for node in data["nodes"]}
    assert all(edge["source"] in ids and edge["target"] in ids for edge in data["edges"])
    assert data["truncated"] is True


def test_search_and_detail():
    repository = InMemoryGraphRepository()
    repository.publish(projection())
    assert repository.search("RAG", "skill_reverse", 10)[0]["id"] == "skill_rag"
    detail = repository.node_detail("skill_rag")
    assert detail is not None
    assert any(item["node"]["id"] == "pos_ai_agent_engineer" for item in detail["adjacent"])
