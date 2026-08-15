from __future__ import annotations

import csv
import hashlib
import time as time_module
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, sessionmaker

from .aggregation import (
    AggregationConfig,
    PositionPosting,
    RequirementEvidence,
    aggregate_requirements,
)
from .catalog_store import load_runtime_catalog
from .config import Settings
from .domain import RequirementType
from .extraction import CatalogExtractor
from .graph import GraphRepository, build_projection
from .models import (
    ChangeEvent,
    GraphVersion,
    JobPosting,
    PipelineRun,
    PositionMention,
    RequirementSnapshot,
    ReviewItem,
    SkillMention,
    utcnow,
)


def _parse_datetime(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"):
            try:
                parsed = datetime.combine(datetime.strptime(raw, pattern).date(), time.min)
                break
            except ValueError:
                continue
        else:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _content_hash(row: dict[str, str]) -> str:
    existing = (row.get("content_hash") or "").strip()
    if len(existing) == 64:
        return existing
    payload = "\n".join((row.get("title", ""), row.get("description", ""), row.get("requirement", "")))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _flags(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(";") if item.strip()]


class PipelineService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        graph_repository: GraphRepository,
        settings: Settings,
    ) -> None:
        self.session_factory = session_factory
        self.graph_repository = graph_repository
        self.settings = settings

    def resolve_source(self, source_file: str) -> Path:
        candidate = Path(source_file)
        if not candidate.is_absolute():
            candidate = self.settings.import_root / candidate
        resolved = candidate.resolve()
        root = self.settings.import_root.resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError("source file must stay inside IMPORT_ROOT")
        if resolved.suffix.lower() != ".csv":
            raise ValueError("only CSV import is supported")
        if not resolved.is_file():
            raise FileNotFoundError(resolved)
        return resolved

    def create_run(self, source_file: str, parameters: dict[str, Any] | None = None) -> PipelineRun:
        source = self.resolve_source(source_file)
        with self.session_factory() as session:
            run = PipelineRun(source_path=str(source), parameters=parameters or {})
            session.add(run)
            session.commit()
            session.refresh(run)
            return run

    def run_now(self, source_file: str, parameters: dict[str, Any] | None = None) -> PipelineRun:
        run = self.create_run(source_file, parameters)
        self.execute(run.id)
        with self.session_factory() as session:
            return session.get(PipelineRun, run.id)  # type: ignore[return-value]

    def claim_next_run(self) -> str | None:
        with self.session_factory() as session:
            run = session.scalar(
                select(PipelineRun)
                .where(PipelineRun.status == "queued")
                .order_by(PipelineRun.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if run is None:
                return None
            run.status = "claimed"
            session.commit()
            return run.id

    def worker(self, poll_seconds: float = 2.0, once: bool = False) -> None:
        while True:
            run_id = self.claim_next_run()
            if run_id:
                try:
                    self.execute(run_id)
                except Exception:
                    # execute() persists the failure. A bad run must not stop
                    # the durable worker from processing later queued runs.
                    pass
            if once:
                return
            if run_id is None:
                time_module.sleep(max(0.1, poll_seconds))

    def execute(self, run_id: str) -> None:
        try:
            self._execute(run_id)
        except Exception as exc:
            with self.session_factory() as session:
                run = session.get(PipelineRun, run_id)
                if run:
                    run.status = "failed"
                    run.error = f"{type(exc).__name__}: {exc}"
                    run.completed_at = utcnow()
                    session.commit()
            raise

    def _execute(self, run_id: str) -> None:
        with self.session_factory() as session:
            run = session.get(PipelineRun, run_id)
            if run is None:
                raise LookupError(f"pipeline run not found: {run_id}")
            run.status = "running"
            run.started_at = utcnow()
            run.error = None
            session.commit()

            source = Path(run.source_path)
            catalog = load_runtime_catalog(session)
            extractor = CatalogExtractor(catalog)
            self._clear_run_outputs(session, run_id)
            imported, invalid = self._ingest_and_extract(session, run, source, extractor)
            session.commit()

            evidence, postings = self._load_evidence(session, run_id)
            parameters = run.parameters or {}
            config = AggregationConfig(
                window_days=int(parameters.get("windowDays", self.settings.default_window_days)),
                min_sample_count=int(parameters.get("minSampleCount", self.settings.min_sample_count)),
                rising_delta=float(parameters.get("risingDelta", 0.12)),
                declining_delta=float(parameters.get("decliningDelta", -0.12)),
            )
            requested_end = parameters.get("windowEnd")
            window_end = date.fromisoformat(requested_end) if requested_end else None
            result = aggregate_requirements(evidence, config, window_end=window_end, postings=postings)
            accepted = []
            review_count = 0
            for item in result.requirements:
                snapshot = RequirementSnapshot(
                    pipeline_run_id=run_id,
                    position_id=item.position_id,
                    skill_id=item.skill_id,
                    window_start=result.window_start,
                    window_end=result.window_end,
                    requirement_type=item.requirement_type.value,
                    weight=item.weight,
                    frequency=item.frequency,
                    confidence=item.confidence,
                    sample_count=item.sample_count,
                    source_ids=item.source_ids,
                    first_seen=item.first_seen,
                    last_seen=item.last_seen,
                    trend=item.trend.value,
                )
                session.add(snapshot)
                previous = session.scalar(
                    select(RequirementSnapshot)
                    .where(
                        RequirementSnapshot.pipeline_run_id != run_id,
                        RequirementSnapshot.position_id == item.position_id,
                        RequirementSnapshot.skill_id == item.skill_id,
                    )
                    .order_by(RequirementSnapshot.created_at.desc())
                    .limit(1)
                )
                if item.trend.value != "stable":
                    session.add(
                        ChangeEvent(
                            pipeline_run_id=run_id,
                            position_id=item.position_id,
                            skill_id=item.skill_id,
                            change_type=item.trend.value,
                            before=(
                                {
                                    "requirementType": previous.requirement_type,
                                    "weight": previous.weight,
                                    "frequency": previous.frequency,
                                }
                                if previous
                                else None
                            ),
                            after={
                                "requirementType": item.requirement_type.value,
                                "weight": item.weight,
                                "frequency": item.frequency,
                            },
                            confidence=item.confidence,
                            evidence_ids=item.source_ids,
                        )
                    )
                if item.confidence >= self.settings.min_auto_publish_confidence:
                    accepted.append(item)
                else:
                    review_count += 1
                    session.add(
                        ReviewItem(
                            pipeline_run_id=run_id,
                            review_type="relationship",
                            subject_id=f"{item.position_id}:{item.skill_id}",
                            title="低置信度岗位技能关系",
                            payload={
                                "positionId": item.position_id,
                                "skillId": item.skill_id,
                                "requirementType": item.requirement_type.value,
                                "weight": item.weight,
                                "frequency": item.frequency,
                            },
                            evidence_ids=item.source_ids,
                            confidence=item.confidence,
                        )
                    )
            session.flush()
            version = f"graph_{result.window_end.isoformat()}_{run_id[-8:]}"
            projection = build_projection(catalog, accepted, version)
            run.status = "publishing"
            run.statistics = {
                "importedRecords": imported,
                "invalidRecords": invalid,
                "positionMentions": session.scalar(
                    select(func.count()).select_from(PositionMention).where(PositionMention.pipeline_run_id == run_id)
                ),
                "linkedDatedPositionPostings": len(postings),
                "skillMentions": session.scalar(
                    select(func.count()).select_from(SkillMention).where(SkillMention.pipeline_run_id == run_id)
                ),
                "datedEvidenceMentions": len(evidence),
                "aggregatedRelationships": len(result.requirements),
                "publishedRelationships": len(accepted),
                "reviewRelationships": review_count,
                "windowStart": result.window_start.isoformat(),
                "windowEnd": result.window_end.isoformat(),
            }
            session.commit()

        self.graph_repository.ensure_schema()
        self.graph_repository.publish(projection)

        with self.session_factory() as session:
            session.execute(update(GraphVersion).where(GraphVersion.status == "active").values(status="inactive"))
            session.add(
                GraphVersion(
                    id=projection.version,
                    pipeline_run_id=run_id,
                    status="active",
                    node_count=len(projection.nodes),
                    edge_count=len(projection.edges),
                )
            )
            run = session.get(PipelineRun, run_id)
            if run:
                run.status = "completed"
                run.completed_at = utcnow()
            session.commit()

    @staticmethod
    def _clear_run_outputs(session: Session, run_id: str) -> None:
        for model in (ChangeEvent, RequirementSnapshot, SkillMention, PositionMention, ReviewItem):
            session.execute(delete(model).where(model.pipeline_run_id == run_id))

    def _ingest_and_extract(
        self,
        session: Session,
        run: PipelineRun,
        source: Path,
        extractor: CatalogExtractor,
    ) -> tuple[int, int]:
        imported = 0
        invalid = 0
        pending_candidates: dict[str, dict[str, Any]] = {}
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required_columns = {"source_id", "source_platform", "company", "title", "description", "requirement", "url"}
            missing = required_columns - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"CSV missing required columns: {', '.join(sorted(missing))}")
            for row in reader:
                source_id = (row.get("source_id") or "").strip()
                title = (row.get("title") or "").strip()
                if not source_id or not title:
                    invalid += 1
                    continue
                posting = JobPosting(
                    source_id=source_id,
                    pipeline_run_id=run.id,
                    source_platform=(row.get("source_platform") or "").strip(),
                    company=(row.get("company") or "").strip(),
                    title=title,
                    category=(row.get("category") or "").strip(),
                    locations=(row.get("locations") or "").strip(),
                    publish_time=_parse_datetime(row.get("publish_time") or ""),
                    description=row.get("description") or "",
                    requirement=row.get("requirement") or "",
                    url=(row.get("url") or "").strip(),
                    content_hash=_content_hash(row),
                    duplicate_group_id=(row.get("duplicate_group_id") or "").strip() or None,
                    quality_flags=_flags(row.get("quality_flags") or ""),
                )
                session.merge(posting)
                linked = extractor.link_position(title)
                session.add(
                    PositionMention(
                        pipeline_run_id=run.id,
                        source_id=source_id,
                        surface=linked.surface,
                        normalized_title=linked.normalized_title,
                        canonical_position_id=linked.position_id,
                        linking_confidence=linked.confidence,
                        status=linked.status,
                    )
                )
                if linked.status == "pending":
                    candidate_key = linked.position_id or linked.normalized_title
                    candidate = pending_candidates.setdefault(
                        candidate_key,
                        {
                            "normalizedTitle": linked.normalized_title,
                            "surfaceForms": set(),
                            "sourceIds": [],
                            "companies": set(),
                            "dates": [],
                            "skills": set(),
                        },
                    )
                    candidate["surfaceForms"].add(title)
                    candidate["sourceIds"].append(source_id)
                    candidate["companies"].add(posting.company)
                    if posting.publish_time:
                        candidate["dates"].append(posting.publish_time.date())
                    candidate["skills"].update(
                        mention.skill_id
                        for mention in extractor.extract_skills(
                            title, posting.category, posting.description, posting.requirement
                        )
                    )
                    imported += 1
                    continue
                for mention in extractor.extract_skills(title, posting.category, posting.description, posting.requirement):
                    session.add(
                        SkillMention(
                            pipeline_run_id=run.id,
                            source_id=source_id,
                            canonical_position_id=linked.position_id or "",
                            canonical_skill_id=mention.skill_id,
                            surface=mention.surface,
                            evidence_text=mention.evidence_text,
                            requirement_type=mention.requirement_type.value,
                            start_offset=mention.start_offset,
                            end_offset=mention.end_offset,
                            extractor=mention.extractor,
                            extraction_confidence=mention.extraction_confidence,
                            linking_confidence=mention.linking_confidence,
                        )
                    )
                imported += 1
        for candidate_id, candidate in pending_candidates.items():
            sample_count = len(set(candidate["sourceIds"]))
            source_count = len({company for company in candidate["companies"] if company})
            dates = candidate["dates"]
            confidence = min(
                0.9,
                0.30 + min(0.30, sample_count / 20) + min(0.20, source_count / 10) + (0.10 if len(dates) >= 2 else 0),
            )
            session.add(
                ReviewItem(
                    pipeline_run_id=run.id,
                    review_type="new_position",
                    subject_id=candidate_id,
                    title=f"候选新岗位：{candidate['normalizedTitle']}",
                    payload={
                        "normalizedTitle": candidate["normalizedTitle"],
                        "surfaceForms": sorted(candidate["surfaceForms"]),
                        "proposedId": "pos_" + candidate_id.removeprefix("candidate_"),
                        "requiredAction": "link_existing_or_create",
                        "sampleCount": sample_count,
                        "sourceCount": source_count,
                        "firstSeen": min(dates).isoformat() if dates else None,
                        "lastSeen": max(dates).isoformat() if dates else None,
                        "candidateSkillIds": sorted(candidate["skills"]),
                    },
                    evidence_ids=sorted(set(candidate["sourceIds"])),
                    confidence=round(confidence, 4),
                )
            )
        return imported, invalid

    @staticmethod
    def _load_evidence(session: Session, run_id: str) -> tuple[list[RequirementEvidence], list[PositionPosting]]:
        mention_rows = session.execute(
            select(SkillMention, JobPosting)
            .join(JobPosting, SkillMention.source_id == JobPosting.source_id)
            .where(SkillMention.pipeline_run_id == run_id)
        ).all()
        evidence: list[RequirementEvidence] = []
        for mention, posting in mention_rows:
            if posting.publish_time is None:
                continue
            evidence.append(
                RequirementEvidence(
                    source_id=posting.source_id,
                    position_id=mention.canonical_position_id,
                    skill_id=mention.canonical_skill_id,
                    company=posting.company,
                    publish_date=posting.publish_time.date(),
                    requirement_type=RequirementType(mention.requirement_type),
                    extraction_confidence=mention.extraction_confidence,
                    linking_confidence=mention.linking_confidence,
                    duplicate_group_id=posting.duplicate_group_id,
                )
            )
        posting_rows = session.execute(
            select(PositionMention, JobPosting)
            .join(JobPosting, PositionMention.source_id == JobPosting.source_id)
            .where(PositionMention.pipeline_run_id == run_id, PositionMention.status == "linked")
        ).all()
        postings = [
            PositionPosting(
                source_id=posting.source_id,
                position_id=mention.canonical_position_id or "",
                publish_date=posting.publish_time.date(),
                duplicate_group_id=posting.duplicate_group_id,
            )
            for mention, posting in posting_rows
            if posting.publish_time is not None and mention.canonical_position_id
        ]
        return evidence, postings
