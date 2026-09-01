from __future__ import annotations

from datetime import datetime
from typing import Literal

from backend.app.demo_data import (
    PANORAMA_EDGES,
    PANORAMA_NODES,
    SKILL_REVERSE_EDGES,
    SKILL_REVERSE_NODES,
    fresh,
    graph_version,
)
from backend.app.services.data_sources import processed_path, read_jsonl


GraphMode = Literal["panorama", "skill_reverse"]


def _graph_parts(mode: GraphMode) -> tuple[list[dict], list[dict], list[str]]:
    rule_nodes = [node for node in read_jsonl(processed_path("graph_nodes.jsonl")) if node.get("mode") == mode]
    rule_edges = [edge for edge in read_jsonl(processed_path("graph_edges.jsonl")) if edge.get("mode") == mode]
    if rule_nodes and rule_edges:
        if mode == "skill_reverse":
            stack_ids = {node["id"] for node in rule_nodes if node.get("type") == "stack"}
            rule_nodes = [node for node in rule_nodes if node.get("type") != "stack"]
            rule_edges = [edge for edge in rule_edges if edge.get("source") not in stack_ids and edge.get("target") not in stack_ids]
        hierarchy = ["cluster", "skill", "position"] if mode == "skill_reverse" else ["cluster", "position", "skill"]
        return rule_nodes, rule_edges, hierarchy

    if mode == "skill_reverse":
        nodes = [node for node in fresh(SKILL_REVERSE_NODES) if node.get("type") != "stack"]
        node_ids = {node["id"] for node in nodes}
        edges = [edge for edge in fresh(SKILL_REVERSE_EDGES) if edge.get("source") in node_ids and edge.get("target") in node_ids]
        return nodes, edges, ["cluster", "skill", "position"]
    return fresh(PANORAMA_NODES), fresh(PANORAMA_EDGES), ["cluster", "position", "skill"]


def _summary(mode: GraphMode, nodes: list[dict]) -> dict:
    return {
        "positionClusterCount": sum(1 for node in nodes if mode == "panorama" and node["type"] == "cluster"),
        "techStackCount": sum(1 for node in nodes if node["type"] == "stack"),
        "skillClusterCount": sum(1 for node in nodes if mode == "skill_reverse" and node["type"] == "cluster"),
        "positionCount": sum(1 for node in nodes if node["type"] == "position"),
        "skillCount": sum(1 for node in nodes if node["type"] == "skill"),
    }


def _filter_graph(nodes: list[dict], edges: list[dict], keyword: str, max_nodes: int) -> tuple[list[dict], list[dict], bool]:
    selected_nodes = nodes
    if keyword:
        lowered = keyword.lower()
        matched_ids = {node["id"] for node in nodes if lowered in node["name"].lower()}
        selected_ids = set(matched_ids)
        for edge in edges:
            if edge["source"] in matched_ids or edge["target"] in matched_ids:
                selected_ids.add(edge["source"])
                selected_ids.add(edge["target"])
        selected_nodes = [node for node in nodes if node["id"] in selected_ids]

    truncated = len(selected_nodes) > max_nodes
    selected_nodes = selected_nodes[:max_nodes]
    selected_ids = {node["id"] for node in selected_nodes}
    selected_edges = [edge for edge in edges if edge["source"] in selected_ids and edge["target"] in selected_ids]
    return selected_nodes, selected_edges, truncated


def get_graph(mode: GraphMode, keyword: str = "", max_nodes: int = 300) -> dict:
    nodes, edges, hierarchy = _graph_parts(mode)
    filtered_nodes, filtered_edges, truncated = _filter_graph(nodes, edges, keyword.strip(), max(1, min(max_nodes, 1000)))
    return {
        "mode": mode,
        "hierarchy": hierarchy,
        "nodes": [_strip_internal_fields(node) for node in filtered_nodes],
        "edges": [_strip_internal_fields(edge) for edge in filtered_edges],
        "summary": _summary(mode, filtered_nodes),
        "updatedAt": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "graphVersion": graph_version(),
        "truncated": truncated,
    }


def get_graph_roots(mode: GraphMode) -> list[dict]:
    nodes, edges, _ = _graph_parts(mode)
    root_type = "cluster"
    roots = []
    for node in nodes:
        if node["type"] != root_type:
            continue
        node_count = 1 + len({edge["source"] for edge in edges if edge["target"] == node["id"]})
        roots.append({"id": node["id"], "name": node["name"], "nodeCount": node_count})
    return roots


def get_graph_node_detail(node_id: str) -> dict:
    for mode in ("panorama", "skill_reverse"):
        nodes, edges, _ = _graph_parts(mode)  # type: ignore[arg-type]
        node_map = {node["id"]: node for node in nodes}
        node = node_map.get(node_id)
        if not node:
            continue

        adjacent_ids = []
        for edge in edges:
            if edge["source"] == node_id:
                adjacent_ids.append(edge["target"])
            elif edge["target"] == node_id:
                adjacent_ids.append(edge["source"])
        adjacent_nodes = [node_map[item_id] for item_id in adjacent_ids if item_id in node_map]

        requires_edges = [edge for edge in edges if edge["relationship"] == "REQUIRES" and edge["source"] == node_id]
        required_skills = []
        preferred_skills = []
        for edge in requires_edges:
            skill = node_map.get(edge["target"])
            if not skill:
                continue
            item = {
                "skillId": skill["id"],
                "name": skill["name"],
                "requirementType": edge.get("requirementType", "required"),
                "weight": edge.get("weight", skill.get("weight", 0)),
                "confidence": edge.get("confidence", node.get("confidence", 0.9)),
            }
            if item["requirementType"] == "required":
                required_skills.append(item)
            else:
                preferred_skills.append(item)

        return {
            "id": node["id"],
            "type": node["type"],
            "name": node["name"],
            "description": _node_description(mode, node),
            "sampleCount": node.get("sampleCount", 0),
            "firstSeen": node.get("firstSeen", ""),
            "confidence": node.get("confidence", 0.9),
            "directNodes": [{"id": item["id"], "type": item["type"], "name": item["name"]} for item in adjacent_nodes],
            "requiredSkills": required_skills,
            "preferredSkills": preferred_skills,
            "relatedPositionCount": sum(1 for item in adjacent_nodes if item["type"] == "position"),
            "skillCount": sum(1 for item in adjacent_nodes if item["type"] == "skill"),
            "clusterCount": sum(1 for item in adjacent_nodes if item["type"] == "cluster"),
            "weight": node.get("weight"),
        }
    raise KeyError(f"unknown nodeId: {node_id}")


def search_graph_nodes(mode: GraphMode, keyword: str, limit: int = 10) -> list[dict]:
    if len(keyword.strip()) < 2:
        return []
    lowered = keyword.strip().lower()
    nodes, _, _ = _graph_parts(mode)
    matches = [
        {"id": node["id"], "type": node["type"], "name": node["name"]}
        for node in nodes
        if lowered in node["name"].lower()
    ]
    return matches[: max(1, min(limit, 30))]


def _strip_internal_fields(item: dict) -> dict:
    return {key: value for key, value in item.items() if key not in {"mode", "generatedAt"}}


def validate_graph_edges() -> dict:
    result = {}
    for mode in ("panorama", "skill_reverse"):
        nodes, edges, _ = _graph_parts(mode)  # type: ignore[arg-type]
        node_ids = {node["id"] for node in nodes}
        invalid_edges = [
            edge
            for edge in edges
            if edge["source"] not in node_ids or edge["target"] not in node_ids
        ]
        result[mode] = {"valid": len(invalid_edges) == 0, "invalidEdges": invalid_edges}
    return result


def _node_description(mode: str, node: dict) -> str:
    if node["type"] == "cluster":
        if mode == "panorama":
            return "岗位簇汇聚职责和技能结构相近的标准岗位，并直接连接岗位层。"
        return "技能簇是技能反查的顶层分类，向下组织含义和用途相近的技能点。"
    if node["type"] == "position":
        return f"{node['name']}的标准岗位画像，可查看所属岗位簇以及直接要求的技能点。"
    return f"{node['name']}是可从 JD 和简历中识别的标准技能点，可反向查看需要该技能的岗位。"
