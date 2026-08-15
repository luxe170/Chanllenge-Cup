from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .catalog import Catalog, NamedDefinition, PositionDefinition, SkillDefinition, load_catalog
from .extraction import normalize_title
from .models import EntityAlias, StandardEntity


def seed_standard_entities(session: Session) -> None:
    catalog = load_catalog()
    entities: list[StandardEntity] = []
    for item in catalog.tech_stacks.values():
        entities.append(StandardEntity(id=item.id, entity_type="tech_stack", name=item.name, description=item.description))
    for item in catalog.skill_clusters.values():
        entities.append(
            StandardEntity(
                id=item.id,
                entity_type="skill_cluster",
                name=item.name,
                description=item.description,
                properties={"parent_id": item.parent_id},
            )
        )
    for item in catalog.position_categories.values():
        entities.append(StandardEntity(id=item.id, entity_type="position_category", name=item.name, description=item.description))
    for item in catalog.skills.values():
        entities.append(
            StandardEntity(
                id=item.id,
                entity_type="skill",
                name=item.name,
                description=item.description,
                properties={"skill_type": item.skill_type, "cluster_id": item.cluster_id},
            )
        )
    for item in catalog.positions.values():
        entities.append(
            StandardEntity(
                id=item.id,
                entity_type="position",
                name=item.name,
                description=item.description,
                status=item.status,
                properties={"category_id": item.category_id},
            )
        )
    for entity in entities:
        if session.get(StandardEntity, entity.id) is None:
            session.add(entity)
    session.flush()

    aliases: list[tuple[str, str, str]] = []
    for item in catalog.positions.values():
        aliases.extend(("position", item.id, alias) for alias in item.aliases)
    for item in catalog.skills.values():
        aliases.extend(("skill", item.id, alias) for alias in item.aliases)
    existing = {
        (row.entity_type, row.normalized_alias)
        for row in session.scalars(select(EntityAlias)).all()
    }
    for entity_type, entity_id, alias in aliases:
        normalized = normalize_title(alias).casefold() if entity_type == "position" else alias.casefold().strip()
        if (entity_type, normalized) not in existing:
            session.add(
                EntityAlias(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    alias=alias,
                    normalized_alias=normalized,
                    source="seed",
                    confidence=1.0,
                )
            )
            existing.add((entity_type, normalized))
    # SessionLocal intentionally disables autoflush. Make newly seeded aliases
    # visible to load_runtime_catalog() during the very first pipeline run.
    session.flush()


def load_runtime_catalog(session: Session) -> Catalog:
    seed_standard_entities(session)
    entities = session.scalars(select(StandardEntity).where(StandardEntity.status != "inactive")).all()
    aliases_by_entity: dict[str, list[str]] = {}
    for alias in session.scalars(select(EntityAlias)).all():
        aliases_by_entity.setdefault(alias.entity_id, []).append(alias.alias)

    positions: dict[str, PositionDefinition] = {}
    skills: dict[str, SkillDefinition] = {}
    categories: dict[str, NamedDefinition] = {}
    clusters: dict[str, NamedDefinition] = {}
    stacks: dict[str, NamedDefinition] = {}
    for entity in entities:
        props = entity.properties or {}
        if entity.entity_type == "position":
            positions[entity.id] = PositionDefinition(
                id=entity.id,
                name=entity.name,
                aliases=tuple(dict.fromkeys([entity.name, *aliases_by_entity.get(entity.id, [])])),
                category_id=props["category_id"],
                description=entity.description,
                status=entity.status,
            )
        elif entity.entity_type == "skill":
            skills[entity.id] = SkillDefinition(
                id=entity.id,
                name=entity.name,
                aliases=tuple(dict.fromkeys([entity.name, *aliases_by_entity.get(entity.id, [])])),
                skill_type=props["skill_type"],
                cluster_id=props["cluster_id"],
                description=entity.description,
            )
        elif entity.entity_type == "position_category":
            categories[entity.id] = NamedDefinition(entity.id, entity.name, None, entity.description)
        elif entity.entity_type == "skill_cluster":
            clusters[entity.id] = NamedDefinition(entity.id, entity.name, props.get("parent_id"), entity.description)
        elif entity.entity_type == "tech_stack":
            stacks[entity.id] = NamedDefinition(entity.id, entity.name, None, entity.description)
    return Catalog(skills, positions, categories, clusters, stacks)
