from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    id: str
    name: str
    aliases: tuple[str, ...]
    skill_type: str
    cluster_id: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class PositionDefinition:
    id: str
    name: str
    aliases: tuple[str, ...]
    category_id: str
    description: str = ""
    status: str = "existing"


@dataclass(frozen=True, slots=True)
class NamedDefinition:
    id: str
    name: str
    parent_id: str | None = None
    description: str = ""


@dataclass(frozen=True, slots=True)
class Catalog:
    skills: dict[str, SkillDefinition]
    positions: dict[str, PositionDefinition]
    position_categories: dict[str, NamedDefinition]
    skill_clusters: dict[str, NamedDefinition]
    tech_stacks: dict[str, NamedDefinition]


def _read_seed(name: str) -> dict[str, Any]:
    path = files("app.seeds").joinpath(name)
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_catalog() -> Catalog:
    skill_data = _read_seed("skills.json")
    position_data = _read_seed("positions.json")
    skills = {
        item["id"]: SkillDefinition(
            id=item["id"],
            name=item["name"],
            aliases=tuple(dict.fromkeys([item["name"], *item.get("aliases", [])])),
            skill_type=item["skill_type"],
            cluster_id=item["cluster_id"],
            description=item.get("description", ""),
        )
        for item in skill_data["skills"]
    }
    positions = {
        item["id"]: PositionDefinition(
            id=item["id"],
            name=item["name"],
            aliases=tuple(dict.fromkeys([item["name"], *item.get("aliases", [])])),
            category_id=item["category_id"],
            description=item.get("description", ""),
            status=item.get("status", "existing"),
        )
        for item in position_data["positions"]
    }
    return Catalog(
        skills=skills,
        positions=positions,
        position_categories={
            item["id"]: NamedDefinition(**item) for item in position_data["position_categories"]
        },
        skill_clusters={
            item["id"]: NamedDefinition(**item) for item in skill_data["skill_clusters"]
        },
        tech_stacks={
            item["id"]: NamedDefinition(**item) for item in skill_data["tech_stacks"]
        },
    )


def reset_catalog_cache() -> None:
    load_catalog.cache_clear()
