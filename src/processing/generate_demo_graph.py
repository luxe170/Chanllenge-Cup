from __future__ import annotations

"""Generate deterministic, clearly labelled demo data for the graph UI."""

from datetime import datetime, timezone
from pathlib import Path

from backend.app.services.data_sources import write_jsonl


CLUSTERS = [
    ("ai", "人工智能研发岗位簇"),
    ("data", "数据技术岗位簇"),
    ("software", "软件研发岗位簇"),
    ("cloud", "云计算与安全岗位簇"),
    ("iot", "智能系统与物联网岗位簇"),
]

POSITIONS = [
    ("agent", "AI Agent 研发工程师", "ai", "new"),
    ("llm", "大模型应用工程师", "ai", "rising"),
    ("cv", "计算机视觉工程师", "ai", "stable"),
    ("data_engineer", "数据研发工程师", "data", "rising"),
    ("data_analyst", "数据分析师", "data", "stable"),
    ("algorithm", "推荐算法工程师", "data", "stable"),
    ("java", "Java 后端工程师", "software", "stable"),
    ("frontend", "前端研发工程师", "software", "stable"),
    ("test", "测试开发工程师", "software", "stable"),
    ("cloud_native", "云原生工程师", "cloud", "rising"),
    ("security", "网络安全工程师", "cloud", "rising"),
    ("devops", "DevOps 工程师", "cloud", "stable"),
    ("embedded", "嵌入式开发工程师", "iot", "stable"),
    ("robot", "机器人算法工程师", "iot", "new"),
    ("edge_ai", "边缘智能工程师", "iot", "new"),
]

SKILLS = [
    ("python", "Python", "ai"), ("pytorch", "PyTorch", "ai"),
    ("llm", "大语言模型", "ai"), ("rag", "RAG", "ai"),
    ("langchain", "LangChain", "ai"), ("prompt", "Prompt 工程", "ai"),
    ("sql", "SQL", "data"), ("spark", "Spark", "data"),
    ("flink", "Flink", "data"), ("hadoop", "Hadoop", "data"),
    ("tableau", "Tableau", "data"), ("statistics", "统计建模", "data"),
    ("java", "Java", "software"), ("spring", "Spring Boot", "software"),
    ("react", "React", "software"), ("typescript", "TypeScript", "software"),
    ("testing", "自动化测试", "software"), ("git", "Git", "software"),
    ("docker", "Docker", "cloud"), ("k8s", "Kubernetes", "cloud"),
    ("linux", "Linux", "cloud"), ("cicd", "CI/CD", "cloud"),
    ("security", "安全攻防", "cloud"), ("microservice", "微服务", "cloud"),
    ("cpp", "C++", "iot"), ("ros", "ROS", "iot"),
    ("embedded_linux", "嵌入式 Linux", "iot"), ("sensor", "传感器融合", "iot"),
    ("edge", "边缘计算", "iot"), ("opencv", "OpenCV", "iot"),
]


def build_demo_graph() -> tuple[list[dict], list[dict]]:
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    nodes: list[dict] = []
    edges: list[dict] = []

    for index, (cluster_key, cluster_name) in enumerate(CLUSTERS):
        nodes.append({"mode": "panorama", "id": f"demo_cluster_{cluster_key}", "name": cluster_name,
                      "type": "cluster", "sampleCount": 90 + index * 23, "confidence": 0.9,
                      "dataKind": "demo", "generatedAt": generated_at})

    for index, (key, name, cluster_key, trend) in enumerate(POSITIONS):
        position_id = f"demo_pos_{key}"
        nodes.append({"mode": "panorama", "id": position_id, "name": name, "type": "position",
                      "trend": trend, "sampleCount": 24 + index * 7, "firstSeen": f"202{3 + index % 3}-0{index % 9 + 1}-15",
                      "confidence": round(0.82 + index % 7 * 0.02, 2), "dataKind": "demo", "generatedAt": generated_at})
        edges.append({"mode": "panorama", "source": position_id, "target": f"demo_cluster_{cluster_key}",
                      "relationship": "BELONGS_TO", "dataKind": "demo", "generatedAt": generated_at})

    for index, (key, name, domain) in enumerate(SKILLS):
        skill_id = f"demo_skill_{key}"
        trend = ("stable", "rising", "new")[index % 3]
        nodes.append({"mode": "panorama", "id": skill_id, "name": name, "type": "skill", "trend": trend,
                      "weight": round(0.56 + index % 9 * 0.045, 2), "sampleCount": 18 + index * 4,
                      "confidence": round(0.81 + index % 8 * 0.02, 2), "dataKind": "demo", "generatedAt": generated_at})

        matching_positions = [item for item in POSITIONS if item[2] == domain]
        for offset in range(2):
            position = matching_positions[(index + offset) % len(matching_positions)]
            weight = round(0.62 + ((index + offset) % 7) * 0.05, 2)
            edges.append({"mode": "panorama", "source": f"demo_pos_{position[0]}", "target": skill_id,
                          "relationship": "REQUIRES", "requirementType": "required" if offset == 0 else "preferred",
                          "weight": weight, "confidence": round(min(0.97, weight + 0.08), 2),
                          "dataKind": "demo", "generatedAt": generated_at})

    # Skill reverse is a different graph projection:
    # tech stack -> skill cluster -> skill -> positions requiring that skill.
    reverse_nodes: list[dict] = []
    reverse_edges: list[dict] = []
    domain_names = {
        "ai": "人工智能技术栈", "data": "大数据技术栈", "software": "软件工程技术栈",
        "cloud": "云计算与安全技术栈", "iot": "智能系统与物联网技术栈",
    }
    cluster_names = {
        "ai": "AI 模型与应用技能簇", "data": "数据计算与分析技能簇",
        "software": "软件工程技能簇", "cloud": "云原生与安全技能簇",
        "iot": "智能硬件与感知技能簇",
    }

    for index, (domain, stack_name) in enumerate(domain_names.items()):
        stack_id = f"reverse_stack_{domain}"
        cluster_id = f"reverse_skill_cluster_{domain}"
        reverse_nodes.append({"mode": "skill_reverse", "id": stack_id, "name": stack_name, "type": "stack",
                              "sampleCount": 120 + index * 31, "confidence": 0.91,
                              "dataKind": "demo", "generatedAt": generated_at})
        reverse_nodes.append({"mode": "skill_reverse", "id": cluster_id, "name": cluster_names[domain], "type": "cluster",
                              "sampleCount": 80 + index * 19, "confidence": 0.89,
                              "dataKind": "demo", "generatedAt": generated_at})
        reverse_edges.append({"mode": "skill_reverse", "source": cluster_id, "target": stack_id,
                              "relationship": "BELONGS_TO", "dataKind": "demo", "generatedAt": generated_at})

    # Five skills from each domain keep this view at exactly 50 nodes:
    # 5 stacks + 5 skill clusters + 25 skills + 15 positions.
    reverse_skills = [skill for domain in domain_names for skill in [item for item in SKILLS if item[2] == domain][:5]]
    for index, (key, name, domain) in enumerate(reverse_skills):
        skill_id = f"reverse_skill_{key}"
        reverse_nodes.append({"mode": "skill_reverse", "id": skill_id, "name": name, "type": "skill",
                              "trend": ("stable", "rising", "new")[index % 3],
                              "weight": round(0.58 + index % 8 * 0.05, 2), "sampleCount": 20 + index * 5,
                              "confidence": round(0.82 + index % 7 * 0.02, 2),
                              "dataKind": "demo", "generatedAt": generated_at})
        reverse_edges.append({"mode": "skill_reverse", "source": skill_id,
                              "target": f"reverse_skill_cluster_{domain}", "relationship": "BELONGS_TO",
                              "dataKind": "demo", "generatedAt": generated_at})

    skills_by_domain = {domain: [item for item in reverse_skills if item[2] == domain] for domain in domain_names}
    for index, (key, name, domain, trend) in enumerate(POSITIONS):
        position_id = f"reverse_pos_{key}"
        reverse_nodes.append({"mode": "skill_reverse", "id": position_id, "name": name, "type": "position",
                              "trend": trend, "sampleCount": 24 + index * 7,
                              "firstSeen": f"202{3 + index % 3}-0{index % 9 + 1}-15",
                              "confidence": round(0.82 + index % 7 * 0.02, 2),
                              "dataKind": "demo", "generatedAt": generated_at})
        domain_skills = skills_by_domain[domain]
        for offset in range(2):
            skill = domain_skills[(index + offset) % len(domain_skills)]
            weight = round(0.66 + ((index + offset) % 6) * 0.05, 2)
            reverse_edges.append({"mode": "skill_reverse", "source": position_id,
                                  "target": f"reverse_skill_{skill[0]}", "relationship": "REQUIRES",
                                  "requirementType": "required" if offset == 0 else "preferred",
                                  "weight": weight, "confidence": round(min(0.97, weight + 0.08), 2),
                                  "dataKind": "demo", "generatedAt": generated_at})

    return nodes + reverse_nodes, edges + reverse_edges


def main() -> None:
    output_dir = Path("data/processed")
    nodes, edges = build_demo_graph()
    write_jsonl(output_dir / "graph_nodes.jsonl", nodes)
    write_jsonl(output_dir / "graph_edges.jsonl", edges)
    panorama_count = sum(node["mode"] == "panorama" for node in nodes)
    print(f"wrote {panorama_count} demo entities in two graph views ({len(nodes)} nodes, {len(edges)} edges)")


if __name__ == "__main__":
    main()
