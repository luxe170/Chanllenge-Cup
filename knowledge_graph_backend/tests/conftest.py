from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMP_ROOT = ROOT / "knowledge_graph_backend_temp" / "pytest_runtime"
TEMP_ROOT.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("GRAPH_BACKEND", "memory")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{(TEMP_ROOT / 'api.db').as_posix()}")
os.environ.setdefault("IMPORT_ROOT", str(TEMP_ROOT))
os.environ.setdefault("ADMIN_API_KEY", "test-admin-key-123")

