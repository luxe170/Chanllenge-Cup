from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _as_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _as_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str
    app_host: str
    app_port: int
    database_url: str
    graph_backend: str
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    neo4j_database: str
    import_root: Path
    default_window_days: int
    min_sample_count: int
    min_auto_publish_confidence: float
    cors_origins: tuple[str, ...]
    admin_api_key: str

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    origins = tuple(
        item.strip()
        for item in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if item.strip()
    )
    settings = Settings(
        app_env=os.getenv("APP_ENV", "development"),
        app_host=os.getenv("APP_HOST", "0.0.0.0"),
        app_port=_as_int("APP_PORT", 8000),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./var/knowledge_graph.db"),
        graph_backend=os.getenv("GRAPH_BACKEND", "neo4j").lower(),
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_username=os.getenv("NEO4J_USERNAME", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "change-me"),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
        import_root=Path(os.getenv("IMPORT_ROOT", "../data/processed")).resolve(),
        default_window_days=_as_int("DEFAULT_WINDOW_DAYS", 90),
        min_sample_count=_as_int("MIN_SAMPLE_COUNT", 2),
        min_auto_publish_confidence=_as_float("MIN_AUTO_PUBLISH_CONFIDENCE", 0.72),
        cors_origins=origins,
        admin_api_key=os.getenv("ADMIN_API_KEY", ""),
    )
    if settings.graph_backend not in {"neo4j", "memory"}:
        raise ValueError("GRAPH_BACKEND must be 'neo4j' or 'memory'")
    if not 0 <= settings.min_auto_publish_confidence <= 1:
        raise ValueError("MIN_AUTO_PUBLISH_CONFIDENCE must be between 0 and 1")
    if settings.is_production and len(settings.admin_api_key) < 16:
        raise ValueError("ADMIN_API_KEY must contain at least 16 characters in production")
    return settings


def reset_settings_cache() -> None:
    get_settings.cache_clear()
