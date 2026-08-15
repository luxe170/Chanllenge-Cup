from __future__ import annotations

from collections import defaultdict, deque
from datetime import date, datetime, timezone
from threading import RLock
from typing import Any, Protocol

from neo4j import GraphDatabase

from .catalog import Catalog
from .domain import (
    AggregatedRequirement,
    GraphEdge,
    GraphNode,
    GraphProjection,
    NodeType,
    RelationshipType,
)


def _serialize(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


def build_projection(
    catalog: Catalog,
    requirements: list[AggregatedRequirement],
    version: str,
) -> GraphProjection:
    position_ids = {item.position_id for item in requirements if item.position_id in catalog.positions}
    skill_ids = {item.skill_id for item in requirements if item.skill_id in catalog.skills}
    category_ids = {catalog.positions[position_id].category_id for position_id in position_ids}
    cluster_ids = {catalog.skills[skill_id].cluster_id for skill_id in skill_ids}
    stack_ids = {catalog.skill_clusters[cluster_id].parent_id for cluster_id in cluster_ids}
    nodes: list[GraphNode] = []

    position_requirements: dict[str, list[AggregatedRequirement]] = defaultdict(list)
    skill_requirements: dict[str, list[AggregatedRequirement]] = defaultdict(list)
    for item in requirements:
        position_requirements[item.position_id].append(item)
        skill_requirements[item.skill_id].append(item)

    for position_id in sorted(position_ids):
        definition = catalog.positions[position_id]
        related = position_requirements[position_id]
        nodes.append(
            GraphNode(
                id=position_id,
                type=NodeType.POSITION,
                name=definition.name,
                properties={
                    "description": definition.description,
                    "aliases": list(definition.aliases),
                    "status": definition.status,
                    "sampleCount": len({source for item in related for source in item.source_ids}),
                    "firstSeen": min(item.first_seen for item in related).isoformat(),
                    "lastSeen": max(item.last_seen for item in related).isoformat(),
                    "confidence": round(sum(item.confidence for item in related) / len(related), 4),
                },
            )
        )
    for category_id in sorted(category_ids):
        definition = catalog.position_categories[category_id]
        nodes.append(
            GraphNode(category_id, NodeType.POSITION_CATEGORY, definition.name, {"description": definition.description})
        )
    for skill_id in sorted(skill_ids):
        definition = catalog.skills[skill_id]
        related = skill_requirements[skill_id]
        nodes.append(
            GraphNode(
                skill_id,
                NodeType.SKILL,
                definition.name,
                {
                    "description": definition.description,
                    "aliases": list(definition.aliases),
                    "skillType": definition.skill_type,
                    "sampleCount": len({source for item in related for source in item.source_ids}),
                    "trend": max(related, key=lambda item: item.weight).trend.value,
                },
            )
        )
    for cluster_id in sorted(cluster_ids):
        definition = catalog.skill_clusters[cluster_id]
        nodes.append(
            GraphNode(cluster_id, NodeType.SKILL_CLUSTER, definition.name, {"description": definition.description})
        )
    for stack_id in sorted(item for item in stack_ids if item):
        definition = catalog.tech_stacks[stack_id]
        nodes.append(GraphNode(stack_id, NodeType.TECH_STACK, definition.name, {"description": definition.description}))

    edges: list[GraphEdge] = []
    for position_id in sorted(position_ids):
        edges.append(
            GraphEdge(
                position_id,
                catalog.positions[position_id].category_id,
                RelationshipType.IN_CATEGORY,
            )
        )
    for skill_id in sorted(skill_ids):
        edges.append(GraphEdge(skill_id, catalog.skills[skill_id].cluster_id, RelationshipType.BELONGS_TO))
    for cluster_id in sorted(cluster_ids):
        parent_id = catalog.skill_clusters[cluster_id].parent_id
        if parent_id:
            edges.append(GraphEdge(cluster_id, parent_id, RelationshipType.BELONGS_TO))
    for item in requirements:
        if item.position_id not in position_ids or item.skill_id not in skill_ids:
            continue
        edges.append(
            GraphEdge(
                item.position_id,
                item.skill_id,
                RelationshipType.REQUIRES,
                {
                    "requirementType": item.requirement_type.value,
                    "weight": item.weight,
                    "frequency": item.frequency,
                    "confidence": item.confidence,
                    "sampleCount": item.sample_count,
                    "sourceIds": item.source_ids,
                    "firstSeen": item.first_seen.isoformat(),
                    "lastSeen": item.last_seen.isoformat(),
                    "trend": item.trend.value,
                    "snapshotId": version,
                },
            )
        )
    return GraphProjection(version, nodes, edges, datetime.now(timezone.utc))


def _filter_projection(
    projection: GraphProjection,
    mode: str,
    root_id: str | None,
    focus_node_id: str | None,
    keyword: str | None,
    max_nodes: int,
) -> dict[str, Any]:
    if mode not in {"panorama", "skill_reverse"}:
        raise ValueError("mode must be panorama or skill_reverse")
    allowed_types = (
        {NodeType.POSITION_CATEGORY, NodeType.POSITION, NodeType.SKILL}
        if mode == "panorama"
        else {NodeType.TECH_STACK, NodeType.SKILL_CLUSTER, NodeType.SKILL, NodeType.POSITION}
    )
    allowed_relations = (
        {RelationshipType.IN_CATEGORY, RelationshipType.REQUIRES}
        if mode == "panorama"
        else {RelationshipType.BELONGS_TO, RelationshipType.REQUIRES}
    )
    nodes_by_id = {node.id: node for node in projection.nodes if node.type in allowed_types}
    edges = [
        edge
        for edge in projection.edges
        if edge.relationship in allowed_relations and edge.source in nodes_by_id and edge.target in nodes_by_id
    ]
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        adjacency[edge.source].add(edge.target)
        adjacency[edge.target].add(edge.source)

    seeds: list[str] = []
    if root_id and root_id in nodes_by_id:
        seeds.append(root_id)
    if focus_node_id and focus_node_id in nodes_by_id:
        seeds.append(focus_node_id)
    if keyword:
        folded = keyword.casefold()
        seeds.extend(node.id for node in nodes_by_id.values() if folded in node.name.casefold())
    selected_ids: list[str]
    if seeds:
        queue = deque(dict.fromkeys(seeds))
        visited: set[str] = set()
        while queue and len(visited) < max_nodes:
            node_id = queue.popleft()
            if node_id in visited:
                continue
            visited.add(node_id)
            queue.extend(sorted(adjacency[node_id] - visited))
        selected_ids = list(visited)
    else:
        type_order = (
            [NodeType.POSITION_CATEGORY, NodeType.POSITION, NodeType.SKILL]
            if mode == "panorama"
            else [NodeType.TECH_STACK, NodeType.SKILL_CLUSTER, NodeType.SKILL, NodeType.POSITION]
        )
        selected_ids = [
            node.id
            for node_type in type_order
            for node in sorted(nodes_by_id.values(), key=lambda item: item.name)
            if node.type == node_type
        ][:max_nodes]
    selected_set = set(selected_ids)
    selected_nodes = [nodes_by_id[node_id] for node_id in selected_ids if node_id in nodes_by_id]
    selected_edges = [edge for edge in edges if edge.source in selected_set and edge.target in selected_set]
    counts = defaultdict(int)
    for node in selected_nodes:
        counts[node.type.value] += 1
    return {
        "mode": mode,
        "hierarchy": (
            ["position_category", "position", "skill"]
            if mode == "panorama"
            else ["tech_stack", "skill_cluster", "skill", "position"]
        ),
        "nodes": [node.as_dict() for node in selected_nodes],
        "edges": [edge.as_dict() for edge in selected_edges],
        "summary": {
            "positionCategoryCount": counts[NodeType.POSITION_CATEGORY.value],
            "techStackCount": counts[NodeType.TECH_STACK.value],
            "skillClusterCount": counts[NodeType.SKILL_CLUSTER.value],
            "positionCount": counts[NodeType.POSITION.value],
            "skillCount": counts[NodeType.SKILL.value],
        },
        "updatedAt": projection.created_at.isoformat(),
        "graphVersion": projection.version,
        "truncated": len(nodes_by_id) > len(selected_nodes),
    }


class GraphRepository(Protocol):
    def ensure_schema(self) -> None: ...
    def health(self) -> dict[str, Any]: ...
    def publish(self, projection: GraphProjection) -> None: ...
    def graph(self, mode: str, root_id: str | None, focus_node_id: str | None, keyword: str | None, max_nodes: int) -> dict[str, Any]: ...
    def roots(self, mode: str) -> list[dict[str, Any]]: ...
    def node_detail(self, node_id: str) -> dict[str, Any] | None: ...
    def search(self, keyword: str, mode: str, limit: int) -> list[dict[str, Any]]: ...
    def close(self) -> None: ...


class InMemoryGraphRepository:
    def __init__(self) -> None:
        self._projection = GraphProjection("empty", [], [], datetime.now(timezone.utc))
        self._lock = RLock()

    def ensure_schema(self) -> None:
        return None

    def health(self) -> dict[str, Any]:
        return {"backend": "memory", "status": "ok", "version": self._projection.version}

    def publish(self, projection: GraphProjection) -> None:
        with self._lock:
            self._projection = projection

    def graph(self, mode: str, root_id: str | None = None, focus_node_id: str | None = None, keyword: str | None = None, max_nodes: int = 300) -> dict[str, Any]:
        with self._lock:
            return _filter_projection(self._projection, mode, root_id, focus_node_id, keyword, max_nodes)

    def roots(self, mode: str) -> list[dict[str, Any]]:
        target = NodeType.POSITION_CATEGORY if mode == "panorama" else NodeType.TECH_STACK
        counts: dict[str, set[str]] = defaultdict(set)
        for edge in self._projection.edges:
            if edge.relationship in {RelationshipType.IN_CATEGORY, RelationshipType.BELONGS_TO}:
                counts[edge.target].add(edge.source)
        return [
            {"id": node.id, "name": node.name, "nodeCount": len(counts[node.id])}
            for node in sorted(self._projection.nodes, key=lambda item: item.name)
            if node.type == target
        ]

    def node_detail(self, node_id: str) -> dict[str, Any] | None:
        node = next((item for item in self._projection.nodes if item.id == node_id), None)
        if node is None:
            return None
        nodes_by_id = {item.id: item for item in self._projection.nodes}
        adjacent: list[dict[str, Any]] = []
        for edge in self._projection.edges:
            if edge.source == node_id:
                other_id = edge.target
            elif edge.target == node_id:
                other_id = edge.source
            else:
                continue
            other = nodes_by_id.get(other_id)
            if other:
                adjacent.append({"node": other.as_dict(), "edge": edge.as_dict()})
        return {**node.as_dict(), "adjacent": adjacent}

    def search(self, keyword: str, mode: str, limit: int = 10) -> list[dict[str, Any]]:
        allowed = (
            {NodeType.POSITION_CATEGORY, NodeType.POSITION, NodeType.SKILL}
            if mode == "panorama"
            else {NodeType.TECH_STACK, NodeType.SKILL_CLUSTER, NodeType.SKILL, NodeType.POSITION}
        )
        folded = keyword.casefold()
        return [
            {"id": node.id, "type": node.type.value, "name": node.name}
            for node in sorted(self._projection.nodes, key=lambda item: (not item.name.casefold().startswith(folded), item.name))
            if node.type in allowed and folded in node.name.casefold()
        ][:limit]

    def close(self) -> None:
        return None


NODE_LABELS = {
    NodeType.POSITION: "Position",
    NodeType.POSITION_CATEGORY: "PositionCategory",
    NodeType.SKILL: "Skill",
    NodeType.SKILL_CLUSTER: "SkillCluster",
    NodeType.TECH_STACK: "TechStack",
}


class Neo4jGraphRepository:
    """Neo4j current-projection repository; evidence and history remain in SQL."""

    def __init__(self, uri: str, username: str, password: str, database: str = "neo4j") -> None:
        self._driver = GraphDatabase.driver(uri, auth=(username, password))
        self._database = database

    def ensure_schema(self) -> None:
        statements = [
            "CREATE CONSTRAINT kg_node_id_unique IF NOT EXISTS FOR (n:KGNode) REQUIRE n.id IS UNIQUE",
            "CREATE INDEX kg_node_name IF NOT EXISTS FOR (n:KGNode) ON (n.name)",
            "CREATE INDEX kg_node_type IF NOT EXISTS FOR (n:KGNode) ON (n.type)",
        ]
        with self._driver.session(database=self._database) as session:
            for statement in statements:
                session.run(statement).consume()

    def health(self) -> dict[str, Any]:
        self._driver.verify_connectivity()
        with self._driver.session(database=self._database) as session:
            record = session.run("MATCH (n:KGNode) RETURN count(n) AS nodes").single()
        return {"backend": "neo4j", "status": "ok", "nodeCount": int(record["nodes"] if record else 0)}

    def publish(self, projection: GraphProjection) -> None:
        nodes_by_type: dict[NodeType, list[dict[str, Any]]] = defaultdict(list)
        for node in projection.nodes:
            payload = {key: _serialize(value) for key, value in node.as_dict().items()}
            payload["graphVersion"] = projection.version
            nodes_by_type[node.type].append(payload)
        edges_by_type: dict[RelationshipType, list[dict[str, Any]]] = defaultdict(list)
        for edge in projection.edges:
            payload = {key: _serialize(value) for key, value in edge.as_dict().items()}
            payload["graphVersion"] = projection.version
            edges_by_type[edge.relationship].append(payload)

        def write(tx):
            tx.run("MATCH (n:KGNode) DETACH DELETE n").consume()
            for node_type, rows in nodes_by_type.items():
                label = NODE_LABELS[node_type]
                tx.run(
                    f"UNWIND $rows AS row CREATE (n:KGNode:{label}) SET n = row",
                    rows=rows,
                ).consume()
            for relationship, rows in edges_by_type.items():
                rel = relationship.value
                tx.run(
                    f"UNWIND $rows AS row MATCH (a:KGNode {{id: row.source}}), (b:KGNode {{id: row.target}}) CREATE (a)-[r:{rel}]->(b) SET r = row",
                    rows=rows,
                ).consume()

        with self._driver.session(database=self._database) as session:
            session.execute_write(write)

    def _export(self, limit: int = 10000) -> GraphProjection:
        with self._driver.session(database=self._database) as session:
            node_records = session.run(
                "MATCH (n:KGNode) RETURN properties(n) AS node LIMIT $limit", limit=limit
            ).data()
            edge_records = session.run(
                "MATCH (a:KGNode)-[r]->(b:KGNode) RETURN a.id AS source, b.id AS target, type(r) AS relationship, properties(r) AS props LIMIT $limit",
                limit=limit * 4,
            ).data()
        nodes = []
        version = "unknown"
        for record in node_records:
            raw = dict(record["node"])
            version = raw.pop("graphVersion", version)
            node_id = raw.pop("id")
            node_type = NodeType(raw.pop("type"))
            name = raw.pop("name")
            nodes.append(GraphNode(node_id, node_type, name, raw))
        edges = []
        for record in edge_records:
            raw = dict(record["props"])
            raw.pop("graphVersion", None)
            raw.pop("source", None)
            raw.pop("target", None)
            raw.pop("relationship", None)
            edges.append(
                GraphEdge(
                    record["source"],
                    record["target"],
                    RelationshipType(record["relationship"]),
                    raw,
                )
            )
        return GraphProjection(version, nodes, edges, datetime.now(timezone.utc))

    def graph(self, mode: str, root_id: str | None = None, focus_node_id: str | None = None, keyword: str | None = None, max_nodes: int = 300) -> dict[str, Any]:
        return _filter_projection(self._export(max(max_nodes * 8, 2000)), mode, root_id, focus_node_id, keyword, max_nodes)

    def roots(self, mode: str) -> list[dict[str, Any]]:
        target_type = NodeType.POSITION_CATEGORY.value if mode == "panorama" else NodeType.TECH_STACK.value
        with self._driver.session(database=self._database) as session:
            rows = session.run(
                "MATCH (root:KGNode {type: $target_type}) OPTIONAL MATCH (child:KGNode)-[:IN_CATEGORY|BELONGS_TO]->(root) RETURN root.id AS id, root.name AS name, count(DISTINCT child) AS nodeCount ORDER BY name",
                target_type=target_type,
            ).data()
        return rows

    def node_detail(self, node_id: str) -> dict[str, Any] | None:
        return InMemoryGraphRepository_from_projection(self._export()).node_detail(node_id)

    def search(self, keyword: str, mode: str, limit: int = 10) -> list[dict[str, Any]]:
        return InMemoryGraphRepository_from_projection(self._export()).search(keyword, mode, limit)

    def close(self) -> None:
        self._driver.close()


def InMemoryGraphRepository_from_projection(projection: GraphProjection) -> InMemoryGraphRepository:
    repository = InMemoryGraphRepository()
    repository.publish(projection)
    return repository

