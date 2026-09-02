from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.app.responses import ok
from backend.app.routers import batches, dashboard, data, graph, llm, matches, resume, reviews
from backend.app.services.evolution_service import (
    compute_change_evidence,
    compute_evolution_changes,
    compute_evidence_detail,
    compute_emerging_positions,
    compute_position_profile,
)

app = FastAPI(
    title="职涯棱镜岗位演化服务",
    version="0.1.0",
    description="""
    职涯棱镜岗位演化服务 API

    适用于岗位能力演化分析、岗位新发现和证据检索等场景。

    主要功能：
    - 查询岗位能力演化变化列表
    - 查看某项能力变化的证据汇总
    - 查看原始 JD 证据详情
    - 查询新兴岗位发现结果

    使用流程：
    1. 调用 /api/v1/evolution/changes 查询演化变化
    2. 使用 change_id 查询该变化的证据
    3. 使用 evidence_id 查看原始 JD 证据详情
    4. 调用 /api/v1/emerging-positions 查看新岗位发现
    """,
    openapi_tags=[
        {"name": "系统", "description": "系统健康检查与基础状态接口"},
        {"name": "岗位演化", "description": "岗位能力演化、证据与变化追踪"},
        {"name": "新岗位发现", "description": "新兴岗位发现与推荐结果"},
    ],
    servers=[{"url": "http://127.0.0.1:8000", "description": "本地开发环境"}],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(data.router)
app.include_router(graph.router)
app.include_router(llm.router)
app.include_router(reviews.router)
app.include_router(resume.router)
app.include_router(matches.router)
app.include_router(batches.router)


@app.get("/health", tags=["系统"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/v1/evolution/changes", tags=["岗位演化"])
def get_evolution_changes(
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    payload = compute_evolution_changes(page=page, page_size=page_size, keyword=keyword or "")
    return ok(payload)


@app.get("/api/v1/evolution/changes/{change_id}/evidence", tags=["岗位演化"])
def get_change_evidence(change_id: str) -> dict:
    try:
        payload = compute_change_evidence(change_id)
        return ok(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/evolution/evidence/{evidence_id}", tags=["岗位演化"])
def get_evidence_detail(evidence_id: str) -> dict:
    try:
        payload = compute_evidence_detail(evidence_id)
        return ok(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/emerging-positions", tags=["新岗位发现"])
def get_emerging_positions(
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    payload = compute_emerging_positions(page=page, page_size=page_size, keyword=keyword or "")
    return ok(payload)


@app.get("/api/v1/positions/{position_id}", tags=["岗位演化"])
def get_position(position_id: str) -> dict:
    try:
        payload = compute_position_profile(position_id)
        return ok(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
