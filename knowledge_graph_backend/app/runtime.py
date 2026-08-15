from __future__ import annotations

from functools import lru_cache

from .config import get_settings
from .graph import GraphRepository, InMemoryGraphRepository, Neo4jGraphRepository


@lru_cache(maxsize=1)
def get_graph_repository() -> GraphRepository:
    settings = get_settings()
    if settings.graph_backend == "memory":
        return InMemoryGraphRepository()
    return Neo4jGraphRepository(
        settings.neo4j_uri,
        settings.neo4j_username,
        settings.neo4j_password,
        settings.neo4j_database,
    )


def reset_graph_repository() -> None:
    if get_graph_repository.cache_info().currsize:
        get_graph_repository().close()
    get_graph_repository.cache_clear()

