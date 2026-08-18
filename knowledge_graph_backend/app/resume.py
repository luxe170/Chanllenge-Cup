"""Parse resume plain text into a structured profile:
basic info, experience blocks, and catalog-linked skills with proficiency.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .catalog import Catalog, load_catalog
from .extraction import CatalogExtractor, normalize_text


PROFICIENCY_LEVELS: tuple[str, ...] = ("熟悉", "掌握", "精通")

_PROFICIENCY_MARKERS: dict[str, tuple[str, ...]] = {
    "精通": ("精通", "expert", "深入研究", "专家"),
    "掌握": ("掌握", "熟练", "熟练掌握", "proficient", "advanced"),
    "熟悉": ("熟悉", "了解", "familiar", "basic", "基础"),
}

_EDUCATION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "博士": ("博士", "PhD", "Ph.D", "Doctor"),
    "硕士": ("硕士", "研究生", "Master", "M.S."),
    "本科": ("本科", "学士", "Bachelor", "B.S.", "B.E."),
    "大专": ("大专", "专科", "Associate"),
}

_INTENTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:意向|求职意向|目标岗位|应聘岗位)[：: 　]+([^\n，。;；]+)"),
    re.compile(r"(?:Target Position|Position Desired)[：: 　]+([^\n，。;；]+)", re.IGNORECASE),
)

_YEARS_PATTERN = re.compile(r"(\d+)\s*(?:\+|余)?\s*年.*?(?:经验|工作|从业)")
_NAME_LABEL = re.compile(r"(?:姓\s*名|Name)[：: 　]+([一-龥A-Za-z· ]{2,20})")
_CHINESE_NAME_LINE = re.compile(r"^([一-龥·]{2,6})$")

# Experience / project section detector: match a date range on a line, capture the
# following line as the title.
_TIME_RANGE = re.compile(
    r"(\d{4}[./年-]\s*\d{1,2}(?:[月]?)?)\s*[-—~到至]\s*(至今|now|present|\d{4}[./年-]\s*\d{1,2}[月]?)",
    re.IGNORECASE,
)


@dataclass(slots=True)
class ResumeSkill:
    id: str
    name: str
    level: str  # 熟悉 / 掌握 / 精通
    source: str
    confidence: float
    requirement_type: str = "resume"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "level": self.level,
            "source": self.source,
            "confidence": round(self.confidence, 3),
        }


@dataclass(slots=True)
class ResumeExperience:
    period: str
    title: str
    detail: str
    tags: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"period": self.period, "title": self.title, "detail": self.detail, "tags": self.tags}


@dataclass(slots=True)
class ResumeProfile:
    name: str
    intendedPosition: str
    education: str
    experienceYears: int | None
    summary: str
    skills: list[ResumeSkill]
    experiences: list[ResumeExperience]
    completeness: int  # 0-100, rough parse-completeness score
    rawText: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "intendedPosition": self.intendedPosition,
            "education": self.education,
            "experienceYears": self.experienceYears,
            "summary": self.summary,
            "skills": [item.as_dict() for item in self.skills],
            "experiences": [item.as_dict() for item in self.experiences],
            "completeness": self.completeness,
        }


def _extract_name(text: str) -> str:
    match = _NAME_LABEL.search(text)
    if match:
        return match.group(1).strip()
    for line in text.splitlines()[:8]:
        stripped = line.strip()
        if not stripped:
            continue
        chinese_match = _CHINESE_NAME_LINE.match(stripped)
        if chinese_match:
            return chinese_match.group(1)
    return ""


def _extract_education(text: str) -> str:
    for label, keywords in _EDUCATION_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                # Try to find "计算机" or a major word within a 30-char window.
                idx = text.find(keyword)
                window = text[max(0, idx - 20): idx + 40]
                major_match = re.search(r"(计算机|软件|电子|信息|数学|自动化|通信|机械|人工智能|数据科学)[一-龥A-Za-z]*", window)
                if major_match:
                    return f"{label} · {major_match.group(0)}"
                return label
    return ""


def _extract_experience_years(text: str) -> int | None:
    match = _YEARS_PATTERN.search(text)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def _extract_intended_position(text: str, name: str) -> str:
    for pattern in _INTENTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    # Fall back to the first line under a heading like "求职意向" alone.
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if re.search(r"(?:求职意向|意向岗位|目标岗位)", line) and idx + 1 < len(lines):
            candidate = lines[idx + 1].strip()
            if candidate and candidate != name:
                return candidate.split()[0]
    return ""


def _extract_experiences(text: str, extractor: CatalogExtractor) -> list[ResumeExperience]:
    lines = text.splitlines()
    experiences: list[ResumeExperience] = []
    for idx, line in enumerate(lines):
        match = _TIME_RANGE.search(line)
        if not match:
            continue
        period = f"{match.group(1)} — {match.group(2)}"
        # Title lives on the same line after the range, or the next non-empty line.
        remainder = line[match.end():].strip(" -—:：|")
        title = remainder
        j = idx + 1
        while not title and j < len(lines):
            candidate = lines[j].strip()
            if candidate:
                title = candidate
                j += 1
                break
            j += 1
        # Collect up to 3 following non-empty lines as detail, stopping at the next date range.
        detail_lines: list[str] = []
        while j < len(lines) and len(detail_lines) < 3:
            candidate = lines[j].strip()
            if _TIME_RANGE.search(candidate):
                break
            if candidate:
                detail_lines.append(candidate)
            j += 1
        detail = " ".join(detail_lines)
        # Find skills tagged inside title + detail.
        skills = extractor.extract_skills("", "", title, detail)
        tags: list[str] = []
        seen: set[str] = set()
        for skill in skills:
            definition = extractor.catalog.skills.get(skill.skill_id)
            if definition and definition.name not in seen:
                seen.add(definition.name)
                tags.append(definition.name)
            if len(tags) >= 5:
                break
        experiences.append(ResumeExperience(period=period, title=title[:80], detail=detail[:200], tags=tags))
        if len(experiences) >= 5:
            break
    return experiences


def _detect_level(context: str) -> str:
    folded = context.casefold()
    for level in ("精通", "掌握", "熟悉"):
        for marker in _PROFICIENCY_MARKERS[level]:
            if marker.casefold() in folded:
                return level
    return "掌握"  # sensible default when no marker is nearby


def _skill_source(context: str) -> str:
    stripped = context.strip().replace("\n", " ")
    if len(stripped) > 60:
        stripped = stripped[:57] + "..."
    return stripped


def _extract_skills(text: str, extractor: CatalogExtractor) -> list[ResumeSkill]:
    # Run the same catalog-driven extractor used for JDs against the whole resume.
    mentions = extractor.extract_skills("", "", text, "")
    # Group by canonical skill; keep the highest-confidence mention and the
    # strongest proficiency marker found across its evidence contexts.
    aggregated: dict[str, dict[str, Any]] = {}
    for mention in mentions:
        definition = extractor.catalog.skills.get(mention.skill_id)
        if definition is None:
            continue
        level = _detect_level(mention.evidence_text)
        confidence = round(mention.extraction_confidence * mention.linking_confidence, 4)
        source = _skill_source(mention.evidence_text)
        record = aggregated.get(mention.skill_id)
        if record is None:
            aggregated[mention.skill_id] = {
                "name": definition.name,
                "level": level,
                "source": source,
                "confidence": confidence,
            }
            continue
        # Prefer the stronger proficiency level; ties resolved by higher confidence.
        current_rank = PROFICIENCY_LEVELS.index(record["level"])
        new_rank = PROFICIENCY_LEVELS.index(level)
        if new_rank > current_rank or (new_rank == current_rank and confidence > record["confidence"]):
            record["level"] = level
            record["source"] = source
            record["confidence"] = confidence
    skills = [
        ResumeSkill(id=skill_id, **payload)
        for skill_id, payload in aggregated.items()
    ]
    skills.sort(key=lambda item: (-PROFICIENCY_LEVELS.index(item.level), -item.confidence))
    return skills


def _completeness(profile: dict[str, Any]) -> int:
    parts = 0
    if profile["name"]:
        parts += 15
    if profile["intendedPosition"]:
        parts += 15
    if profile["education"]:
        parts += 15
    if profile["experienceYears"] is not None:
        parts += 10
    if profile["experiences"]:
        parts += min(20, 10 * len(profile["experiences"]))
    if profile["skills"]:
        parts += min(25, 5 * len(profile["skills"]))
    return min(100, parts)


def parse_resume_text(text: str, catalog: Catalog | None = None) -> ResumeProfile:
    """Turn ``text`` extracted from a resume into a :class:`ResumeProfile`."""

    if not text or not text.strip():
        raise ValueError("resume text is empty")
    catalog = catalog or load_catalog()
    extractor = CatalogExtractor(catalog)
    normalized = normalize_text(text)

    name = _extract_name(normalized)
    intended = _extract_intended_position(normalized, name)
    education = _extract_education(normalized)
    years = _extract_experience_years(normalized)
    experiences = _extract_experiences(normalized, extractor)
    skills = _extract_skills(normalized, extractor)
    summary_bits: list[str] = []
    if intended:
        summary_bits.append(f"意向：{intended}")
    if years is not None:
        summary_bits.append(f"{years} 年相关经验")
    if not summary_bits and experiences:
        summary_bits.append(experiences[0].title)
    summary = " · ".join(summary_bits) if summary_bits else "AI 方向工程师"

    profile_dict = {
        "name": name,
        "intendedPosition": intended,
        "education": education,
        "experienceYears": years,
        "experiences": [item.as_dict() for item in experiences],
        "skills": [item.as_dict() for item in skills],
    }
    completeness = _completeness(profile_dict)
    return ResumeProfile(
        name=name,
        intendedPosition=intended,
        education=education,
        experienceYears=years,
        summary=summary,
        skills=skills,
        experiences=experiences,
        completeness=completeness,
        rawText=normalized,
    )
