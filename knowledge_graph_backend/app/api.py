from __future__ import annotations

import secrets
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .catalog_store import load_runtime_catalog
from .config import Settings, get_settings
from .database import SessionLocal, get_session
from .evaluation import extraction_metrics
from .extraction import normalize_title
from .models import (
    ChangeEvent,
    EntityAlias,
    GoldAnnotation,
    GraphVersion,
    JobPosting,
    PipelineRun,
    RequirementSnapshot,
    ReviewItem,
    SkillMention,
    StandardEntity,
    utcnow,
)
from .pipeline import PipelineService
from .runtime import get_graph_repository
from .schemas import EntityCreate, GoldAnnotationCreate, PipelineRunCreate, ReviewDecision


router = APIRouter(prefix="/api/v1")
SessionDep = Annotated[Session, Depends(get_session)]
GraphMode = Literal["panorama", "skill_reverse"]


def _response(request: Request, data: Any) -> dict[str, Any]:
    return {"data": data, "requestId": request.state.request_id}


def _run_view(run: PipelineRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "status": run.status,
        "sourcePath": run.source_path,
        "parameters": run.parameters,
        "statistics": run.statistics,
        "error": run.error,
        "createdAt": run.created_at,
        "startedAt": run.started_at,
        "completedAt": run.completed_at,
    }


def _pipeline_service() -> PipelineService:
    return PipelineService(SessionLocal, get_graph_repository(), get_settings())


def require_admin(
    settings: Annotated[Settings, Depends(get_settings)],
    x_admin_key: Annotated[str | None, Header()] = None,
) -> None:
    if not settings.admin_api_key and not settings.is_production:
        return
    if not x_admin_key or not secrets.compare_digest(x_admin_key, settings.admin_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin key")


def _frontend_compat(graph: dict[str, Any]) -> dict[str, Any]:
    output = dict(graph)
    node_mapping = {"position_category": "cluster", "skill_cluster": "cluster", "tech_stack": "stack"}
    output["nodes"] = [
        {**node, "type": node_mapping.get(node["type"], node["type"])} for node in graph["nodes"]
    ]
    output["edges"] = [
        {**edge, "relationship": "BELONGS_TO" if edge["relationship"] == "IN_CATEGORY" else edge["relationship"]}
        for edge in graph["edges"]
    ]
    output["hierarchy"] = [node_mapping.get(item, item) for item in graph["hierarchy"]]
    summary = dict(graph["summary"])
    summary["positionClusterCount"] = summary.pop("positionCategoryCount", 0)
    output["summary"] = summary
    return output


@router.get("/health")
def health(request: Request, session: SessionDep):
    session.execute(text("SELECT 1"))
    graph_status: dict[str, Any]
    overall = "ok"
    try:
        graph_status = get_graph_repository().health()
    except Exception as exc:
        overall = "degraded"
        graph_status = {"status": "unavailable", "error": type(exc).__name__}
    return _response(request, {"status": overall, "database": "ok", "graph": graph_status})


@router.get("/dashboard/summary")
def dashboard_summary(request: Request, session: SessionDep):
    valid_count = session.scalar(select(func.count()).select_from(JobPosting)) or 0
    emerging_count = session.scalar(
        select(func.count()).select_from(StandardEntity).where(
            StandardEntity.entity_type == "position", StandardEntity.status == "emerging"
        )
    ) or 0
    changed_count = session.scalar(select(func.count()).select_from(ChangeEvent)) or 0
    metrics = extraction_metrics(session)
    return _response(
        request,
        {
            "sourceCount": session.scalar(select(func.count(func.distinct(JobPosting.source_platform)))) or 0,
            "validCount": valid_count,
            "emergingCount": emerging_count,
            "changedCount": changed_count,
            "metrics": metrics,
        },
    )


@router.get("/graph")
def graph(
    request: Request,
    mode: GraphMode,
    rootId: str | None = None,
    focusNodeId: str | None = None,
    keyword: str | None = None,
    maxNodes: int = Query(default=300, ge=1, le=1000),
    contract: Literal["canonical", "frontend_v1"] = "canonical",
):
    data = get_graph_repository().graph(mode, rootId, focusNodeId, keyword, maxNodes)
    return _response(request, _frontend_compat(data) if contract == "frontend_v1" else data)


@router.get("/graph/roots")
def graph_roots(request: Request, mode: GraphMode):
    return _response(request, get_graph_repository().roots(mode))


@router.get("/graph/nodes/{node_id}")
def graph_node(request: Request, node_id: str):
    node = get_graph_repository().node_detail(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="node not found")
    return _response(request, node)


@router.get("/graph/search")
def graph_search(
    request: Request,
    keyword: str = Query(min_length=2),
    mode: GraphMode = "panorama",
    limit: int = Query(default=10, ge=1, le=30),
):
    return _response(request, get_graph_repository().search(keyword, mode, limit))


@router.get("/positions/{position_id}")
def position_detail(request: Request, position_id: str, session: SessionDep):
    entity = session.get(StandardEntity, position_id)
    if entity is None or entity.entity_type != "position":
        raise HTTPException(status_code=404, detail="position not found")
    latest = session.scalars(
        select(RequirementSnapshot)
        .where(RequirementSnapshot.position_id == position_id)
        .order_by(RequirementSnapshot.window_end.desc(), RequirementSnapshot.weight.desc())
    ).all()
    latest_by_skill: dict[str, RequirementSnapshot] = {}
    for item in latest:
        latest_by_skill.setdefault(item.skill_id, item)
    skills = {row.id: row for row in session.scalars(select(StandardEntity).where(StandardEntity.entity_type == "skill")).all()}
    return _response(
        request,
        {
            "id": entity.id,
            "name": entity.name,
            "description": entity.description,
            "status": entity.status,
            "categoryId": (entity.properties or {}).get("category_id"),
            "requirements": [
                {
                    "id": row.skill_id,
                    "name": skills[row.skill_id].name if row.skill_id in skills else row.skill_id,
                    "requirementType": row.requirement_type,
                    "weight": row.weight,
                    "frequency": row.frequency,
                    "confidence": row.confidence,
                    "trend": row.trend,
                    "firstSeen": row.first_seen,
                    "lastSeen": row.last_seen,
                    "evidenceCount": row.sample_count,
                }
                for row in latest_by_skill.values()
            ],
        },
    )


@router.get("/positions/{position_id}/evidence")
def position_evidence(
    request: Request,
    position_id: str,
    session: SessionDep,
    skillId: str | None = None,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
):
    query = (
        select(SkillMention, JobPosting)
        .join(JobPosting, SkillMention.source_id == JobPosting.source_id)
        .where(SkillMention.canonical_position_id == position_id)
    )
    if skillId:
        query = query.where(SkillMention.canonical_skill_id == skillId)
    rows = session.execute(query.order_by(JobPosting.publish_time.desc()).offset((page - 1) * pageSize).limit(pageSize)).all()
    return _response(
        request,
        {
            "items": [
                {
                    "sourceId": posting.source_id,
                    "company": posting.company,
                    "title": posting.title,
                    "publishTime": posting.publish_time,
                    "skillId": mention.canonical_skill_id,
                    "requirementType": mention.requirement_type,
                    "evidenceText": mention.evidence_text,
                    "confidence": round(mention.extraction_confidence * mention.linking_confidence, 4),
                    "url": posting.url,
                }
                for mention, posting in rows
            ],
            "page": page,
            "pageSize": pageSize,
        },
    )


@router.get("/skills/{skill_id}")
def skill_detail(request: Request, skill_id: str, session: SessionDep):
    entity = session.get(StandardEntity, skill_id)
    if entity is None or entity.entity_type != "skill":
        raise HTTPException(status_code=404, detail="skill not found")
    node = get_graph_repository().node_detail(skill_id)
    return _response(request, {"id": entity.id, "name": entity.name, "description": entity.description, **(entity.properties or {}), "graph": node})


@router.get("/evolution/changes")
def evolution_changes(
    request: Request,
    session: SessionDep,
    keyword: str | None = None,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
):
    entities = {row.id: row.name for row in session.scalars(select(StandardEntity)).all()}
    query = select(ChangeEvent).order_by(ChangeEvent.detected_at.desc())
    rows = session.scalars(query).all()
    if keyword:
        folded = keyword.casefold()
        rows = [row for row in rows if folded in entities.get(row.position_id, row.position_id).casefold() or folded in entities.get(row.skill_id, row.skill_id).casefold()]
    total = len(rows)
    rows = rows[(page - 1) * pageSize: page * pageSize]
    return _response(
        request,
        {
            "items": [
                {
                    "id": row.id,
                    "positionId": row.position_id,
                    "positionName": entities.get(row.position_id, row.position_id),
                    "skillId": row.skill_id,
                    "skillName": entities.get(row.skill_id, row.skill_id),
                    "changeType": row.change_type,
                    "before": row.before,
                    "after": row.after,
                    "evidenceCount": len(row.evidence_ids),
                    "confidence": row.confidence,
                    "detectedAt": row.detected_at,
                }
                for row in rows
            ],
            "total": total,
            "page": page,
            "pageSize": pageSize,
        },
    )


@router.get("/evolution/changes/{change_id}/evidence")
def change_evidence(request: Request, change_id: str, session: SessionDep):
    row = session.get(ChangeEvent, change_id)
    if row is None:
        raise HTTPException(status_code=404, detail="change not found")
    return _response(
        request,
        {
            "changeId": row.id,
            "positionId": row.position_id,
            "skillId": row.skill_id,
            "before": row.before,
            "after": row.after,
            "confidence": row.confidence,
            "evidenceIds": row.evidence_ids,
        },
    )


@router.get("/evolution/evidence/{source_id:path}")
def raw_evidence(request: Request, source_id: str, session: SessionDep):
    posting = session.get(JobPosting, source_id)
    if posting is None:
        raise HTTPException(status_code=404, detail="evidence not found")
    mentions = session.scalars(select(SkillMention).where(SkillMention.source_id == source_id)).all()
    return _response(
        request,
        {
            "sourceId": posting.source_id,
            "company": posting.company,
            "title": posting.title,
            "sourcePlatform": posting.source_platform,
            "publishTime": posting.publish_time,
            "url": posting.url,
            "description": posting.description,
            "requirement": posting.requirement,
            "mentions": [
                {"skillId": item.canonical_skill_id, "evidenceText": item.evidence_text, "requirementType": item.requirement_type}
                for item in mentions
            ],
        },
    )


@router.get("/emerging-positions")
def emerging_positions(
    request: Request,
    session: SessionDep,
    keyword: str | None = None,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
):
    query = select(StandardEntity).where(StandardEntity.entity_type == "position", StandardEntity.status == "emerging")
    rows = session.scalars(query.order_by(StandardEntity.name)).all()
    if keyword:
        rows = [row for row in rows if keyword.casefold() in row.name.casefold()]
    total = len(rows)
    rows = rows[(page - 1) * pageSize:page * pageSize]
    return _response(
        request,
        {
            "items": [
                {"positionId": row.id, "name": row.name, "description": row.description, "confidence": 1.0, "status": row.status}
                for row in rows
            ],
            "total": total,
            "page": page,
            "pageSize": pageSize,
        },
    )


@router.post("/pipeline-runs", status_code=202, dependencies=[Depends(require_admin)])
def create_pipeline_run(request: Request, payload: PipelineRunCreate):
    service = _pipeline_service()
    try:
        run = service.create_run(payload.sourceFile, payload.parameters)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _response(request, _run_view(run))


@router.get("/pipeline-runs")
def list_pipeline_runs(request: Request, session: SessionDep, limit: int = Query(default=20, ge=1, le=100)):
    rows = session.scalars(select(PipelineRun).order_by(PipelineRun.created_at.desc()).limit(limit)).all()
    return _response(request, [_run_view(row) for row in rows])


@router.get("/pipeline-runs/{run_id}")
def get_pipeline_run(request: Request, run_id: str, session: SessionDep):
    run = session.get(PipelineRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="pipeline run not found")
    return _response(request, _run_view(run))


@router.post("/pipeline-runs/{run_id}/retry", status_code=202, dependencies=[Depends(require_admin)])
def retry_pipeline_run(request: Request, run_id: str, session: SessionDep):
    run = session.get(PipelineRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="pipeline run not found")
    if run.status != "failed":
        raise HTTPException(status_code=409, detail="only failed runs can be retried")
    run.status = "queued"
    run.error = None
    run.started_at = None
    run.completed_at = None
    session.commit()
    return _response(request, _run_view(run))


@router.get("/reviews")
def reviews(
    request: Request,
    session: SessionDep,
    reviewStatus: Literal["pending", "approved", "rejected"] | None = None,
    reviewType: str | None = None,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
):
    query = select(ReviewItem)
    if reviewStatus:
        query = query.where(ReviewItem.status == reviewStatus)
    if reviewType:
        query = query.where(ReviewItem.review_type == reviewType)
    rows = session.scalars(query.order_by(ReviewItem.created_at.desc())).all()
    total = len(rows)
    rows = rows[(page - 1) * pageSize:page * pageSize]
    return _response(request, {"items": [{"id": row.id, "type": row.review_type, "title": row.title, "payload": row.payload, "evidenceIds": row.evidence_ids, "confidence": row.confidence, "status": row.status, "createdAt": row.created_at} for row in rows], "total": total, "page": page, "pageSize": pageSize})


@router.post("/reviews/{review_id}/decision", dependencies=[Depends(require_admin)])
def review_decision(request: Request, review_id: str, payload: ReviewDecision, session: SessionDep):
    row = session.get(ReviewItem, review_id)
    if row is None:
        raise HTTPException(status_code=404, detail="review item not found")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="review item has already been decided")
    if payload.decision == "approved" and row.review_type == "new_position":
        action = payload.modifications.get("action")
        canonical_id = payload.modifications.get("canonicalId")
        if action == "link_existing":
            entity = session.get(StandardEntity, canonical_id)
            if entity is None or entity.entity_type != "position":
                raise HTTPException(status_code=400, detail="canonicalId is not an existing position")
        elif action == "create":
            canonical_id = canonical_id or row.payload.get("proposedId")
            name = payload.modifications.get("canonicalName") or row.payload.get("normalizedTitle")
            category_id = payload.modifications.get("categoryId")
            category = session.get(StandardEntity, category_id)
            if not canonical_id or not str(canonical_id).startswith("pos_") or category is None or category.entity_type != "position_category":
                raise HTTPException(status_code=400, detail="create requires canonicalId and a valid categoryId")
            if session.get(StandardEntity, canonical_id) is None:
                session.add(StandardEntity(id=canonical_id, entity_type="position", name=name, description=payload.modifications.get("description", ""), status="emerging", properties={"category_id": category_id}))
        else:
            raise HTTPException(status_code=400, detail="new position approval requires action=create or link_existing")
        alias = row.payload.get("normalizedTitle")
        normalized_alias = normalize_title(alias).casefold()
        exists = session.scalar(select(EntityAlias).where(EntityAlias.entity_type == "position", EntityAlias.normalized_alias == normalized_alias))
        if exists is None:
            session.add(EntityAlias(entity_type="position", entity_id=canonical_id, alias=alias, normalized_alias=normalized_alias, source="review", confidence=1.0))
    row.status = payload.decision
    row.decision_note = payload.note
    row.decided_at = utcnow()
    session.commit()
    return _response(request, {"id": row.id, "status": row.status})


@router.post("/entities", status_code=201, dependencies=[Depends(require_admin)])
def create_entity(request: Request, payload: EntityCreate, session: SessionDep):
    if session.get(StandardEntity, payload.id):
        raise HTTPException(status_code=409, detail="entity id already exists")
    expected_prefix = {
        "position": "pos_",
        "position_category": "category_",
        "skill": "skill_",
        "skill_cluster": "cluster_",
        "tech_stack": "stack_",
    }[payload.entityType]
    if not payload.id.startswith(expected_prefix):
        raise HTTPException(status_code=400, detail=f"{payload.entityType} id must start with {expected_prefix}")
    properties = payload.properties
    if payload.entityType == "position":
        parent = session.get(StandardEntity, properties.get("category_id"))
        if parent is None or parent.entity_type != "position_category":
            raise HTTPException(status_code=400, detail="position requires a valid category_id")
    elif payload.entityType == "skill":
        parent = session.get(StandardEntity, properties.get("cluster_id"))
        allowed_skill_types = {"language", "framework", "tool", "database", "method", "knowledge", "soft_skill"}
        if parent is None or parent.entity_type != "skill_cluster":
            raise HTTPException(status_code=400, detail="skill requires a valid cluster_id")
        if properties.get("skill_type") not in allowed_skill_types:
            raise HTTPException(status_code=400, detail="skill requires a valid skill_type")
    elif payload.entityType == "skill_cluster":
        parent = session.get(StandardEntity, properties.get("parent_id"))
        if parent is None or parent.entity_type != "tech_stack":
            raise HTTPException(status_code=400, detail="skill_cluster requires a valid parent_id")
    entity = StandardEntity(id=payload.id, entity_type=payload.entityType, name=payload.name, description=payload.description, status=payload.status, properties=payload.properties)
    session.add(entity)
    for alias in dict.fromkeys([payload.name, *payload.aliases]):
        normalized = normalize_title(alias).casefold() if payload.entityType == "position" else alias.casefold().strip()
        session.add(EntityAlias(entity_type=payload.entityType, entity_id=payload.id, alias=alias, normalized_alias=normalized, source="manual", confidence=1.0))
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="entity name or alias already exists") from exc
    return _response(request, {"id": entity.id, "type": entity.entity_type, "name": entity.name})


@router.post("/gold-annotations", status_code=201, dependencies=[Depends(require_admin)])
def create_gold_annotation(request: Request, payload: GoldAnnotationCreate, session: SessionDep):
    if payload.endOffset is not None and payload.startOffset is not None and payload.endOffset < payload.startOffset:
        raise HTTPException(status_code=400, detail="endOffset must not be less than startOffset")
    row = GoldAnnotation(source_id=payload.sourceId, annotation_type=payload.annotationType, canonical_id=payload.canonicalId, requirement_type=payload.requirementType, start_offset=payload.startOffset, end_offset=payload.endOffset, annotator=payload.annotator)
    session.add(row)
    session.commit()
    return _response(request, {"id": row.id})


@router.get("/evaluations/extraction")
def evaluate_extraction(request: Request, session: SessionDep, runId: str | None = None):
    return _response(request, extraction_metrics(session, runId))


@router.get("/evaluations/summary")
def evaluation_summary(request: Request, session: SessionDep):
    extraction = extraction_metrics(session)
    return _response(request, {"jdExtraction": extraction, "resumeExtraction": {"status": "not_owned_by_graph_backend"}, "matching": {"status": "not_owned_by_graph_backend"}})


@router.get("/graph/versions")
def graph_versions(request: Request, session: SessionDep):
    rows = session.scalars(select(GraphVersion).order_by(GraphVersion.created_at.desc())).all()
    return _response(request, [{"id": row.id, "pipelineRunId": row.pipeline_run_id, "status": row.status, "nodeCount": row.node_count, "edgeCount": row.edge_count, "createdAt": row.created_at} for row in rows])
