from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from backend.app.responses import ok
from backend.app.services.graph_service import get_graph, get_graph_node_detail, get_graph_roots, search_graph_nodes

router = APIRouter(prefix="/api/v1", tags=["岗位图谱"])


@router.get("/graph")
def graph(
    mode: Literal["panorama", "skill_reverse"] = Query(default="panorama"),
    keyword: str = Query(default=""),
    max_nodes: int = Query(default=300, ge=1, le=1000),
) -> dict:
    return ok(get_graph(mode=mode, keyword=keyword, max_nodes=max_nodes))


@router.get("/graph/roots")
def graph_roots(
    mode: Literal["panorama", "skill_reverse"] = Query(default="panorama"),
) -> dict:
    return ok(get_graph_roots(mode))


@router.get("/graph/nodes/{node_id}")
def graph_node_detail(node_id: str) -> dict:
    try:
        return ok(get_graph_node_detail(node_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/graph/search")
def graph_search(
    keyword: str = Query(),
    mode: Literal["panorama", "skill_reverse"] = Query(default="panorama"),
    limit: int = Query(default=10, ge=1, le=30),
) -> dict:
    return ok(search_graph_nodes(mode=mode, keyword=keyword, limit=limit))
