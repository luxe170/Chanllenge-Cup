from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

from .catalog import Catalog, PositionDefinition, SkillDefinition
from .domain import ExtractedSkill, LinkedPosition, RequirementType


TITLE_NOISE = re.compile(
    r"(?:[-—_|/（(]\s*)?(?:北京|上海|深圳|广州|杭州|成都|武汉|西安|南京|苏州|重庆|校招|社招|实习|应届|专家|高级|资深|初级|中级|负责人|经理|总监|\d+[-~—至]\d+年|[Pp]\d+)(?:\s*[）)])?",
    re.IGNORECASE,
)
WHITESPACE = re.compile(r"\s+")
PREFERRED_MARKERS = ("优先", "加分", "bonus", "更佳", "preferred", "有经验者")
REQUIRED_MARKERS = ("必须", "要求", "熟练", "精通", "掌握", "具备", "熟悉", "required")


def normalize_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value or "").replace("\r\n", "\n").replace("\r", "\n")


def normalize_title(title: str) -> str:
    text = normalize_text(title)
    text = re.sub(r"^\s*[A-Z]?\d{3,}\s*[-_:：]?\s*", "", text)
    text = TITLE_NOISE.sub(" ", text)
    text = WHITESPACE.sub(" ", text).strip(" -—_|/（）()")
    parts = re.split(r"\s*[-—|]\s*", text, maxsplit=1)
    if len(parts) == 2 and re.search(r"工程师|开发|算法|架构师|设计师|研究员|专家|顾问", parts[0]):
        text = parts[0].strip()
    return text


def _alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(normalize_text(alias))
    if re.fullmatch(r"[A-Za-z0-9_.+#/ -]+", alias):
        return re.compile(rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])", re.IGNORECASE)
    return re.compile(escaped, re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class _SkillPattern:
    definition: SkillDefinition
    alias: str
    pattern: re.Pattern[str]


class CatalogExtractor:
    """Deterministic high-precision extractor with evidence offsets."""

    def __init__(self, catalog: Catalog):
        self.catalog = catalog
        patterns: list[_SkillPattern] = []
        for definition in catalog.skills.values():
            for alias in definition.aliases:
                patterns.append(_SkillPattern(definition, alias, _alias_pattern(alias)))
        self._skill_patterns = sorted(patterns, key=lambda item: len(item.alias), reverse=True)
        self._position_aliases: list[tuple[PositionDefinition, str, re.Pattern[str]]] = []
        for definition in catalog.positions.values():
            for alias in definition.aliases:
                self._position_aliases.append((definition, alias, _alias_pattern(alias)))
        self._position_aliases.sort(key=lambda item: len(item[1]), reverse=True)

    def link_position(self, title: str) -> LinkedPosition:
        normalized = normalize_title(title)
        for definition, alias, pattern in self._position_aliases:
            if pattern.search(normalized):
                exact = normalized.casefold() == normalize_title(alias).casefold()
                return LinkedPosition(
                    surface=title,
                    normalized_title=normalized,
                    position_id=definition.id,
                    confidence=0.98 if exact else 0.90,
                    status="linked",
                )
        folded = normalized.casefold()
        heuristic_rules = (
            ("pos_ai_agent_engineer", ("agent", "智能体")),
            ("pos_llm_algorithm_engineer", ("大模型", "llm")),
            ("pos_nlp_engineer", ("nlp", "自然语言", "语言算法")),
            ("pos_cv_engineer", ("计算机视觉", "视觉算法", "图像算法", "cv算法")),
            ("pos_machine_learning_engineer", ("算法", "机器学习", "深度学习")),
            ("pos_java_backend", ("java",)),
            ("pos_go_backend", ("golang", "go开发", "go后端", "go语言")),
            ("pos_python_backend", ("python开发", "python后端")),
            ("pos_frontend_engineer", ("前端", "web开发")),
            ("pos_data_engineer", ("大数据", "数据开发", "数据工程", "数据平台")),
            ("pos_devops_engineer", ("devops", "sre", "运维开发", "可靠性")),
            ("pos_cloud_engineer", ("云原生", "云平台", "云计算")),
            ("pos_security_engineer", ("安全",)),
            ("pos_embedded_engineer", ("嵌入式", "物联网", "固件")),
            ("pos_test_engineer", ("测试", "质量")),
        )
        for position_id, hints in heuristic_rules:
            if position_id in self.catalog.positions and any(hint in folded for hint in hints):
                return LinkedPosition(
                    surface=title,
                    normalized_title=normalized,
                    position_id=position_id,
                    confidence=0.82,
                    status="linked",
                )
        candidate_id = "candidate_" + hashlib.sha1(normalized.casefold().encode("utf-8")).hexdigest()[:16]
        return LinkedPosition(
            surface=title,
            normalized_title=normalized,
            position_id=candidate_id,
            confidence=0.35,
            status="pending",
        )

    def extract_skills(self, title: str, category: str, description: str, requirement: str) -> list[ExtractedSkill]:
        text = normalize_text("\n".join((title, category, description, requirement)))
        candidates: list[ExtractedSkill] = []
        occupied: list[tuple[int, int]] = []

        for item in self._skill_patterns:
            for match in item.pattern.finditer(text):
                start, end = match.span()
                if any(start < used_end and end > used_start for used_start, used_end in occupied):
                    continue
                context_start = max(0, start - 70)
                context_end = min(len(text), end + 70)
                context = text[context_start:context_end]
                context_folded = context.casefold()
                mention_center = ((start + end) // 2) - context_start

                def nearest(markers: tuple[str, ...]) -> int | None:
                    distances = []
                    for marker in markers:
                        offset = context_folded.find(marker)
                        while offset >= 0:
                            distances.append(abs((offset + len(marker) // 2) - mention_center))
                            offset = context_folded.find(marker, offset + 1)
                    return min(distances) if distances else None

                preferred_distance = nearest(PREFERRED_MARKERS)
                required_distance = nearest(REQUIRED_MARKERS)
                preferred = preferred_distance is not None
                required = required_distance is not None
                requirement_type = (
                    RequirementType.PREFERRED
                    if preferred and (required_distance is None or preferred_distance < required_distance)
                    else RequirementType.REQUIRED
                )
                evidence_start = text.rfind("\n", context_start, start)
                evidence_start = context_start if evidence_start < 0 else evidence_start + 1
                evidence_end = text.find("\n", end, context_end)
                evidence_end = context_end if evidence_end < 0 else evidence_end
                alias_is_canonical = match.group(0).casefold() == item.definition.name.casefold()
                candidates.append(
                    ExtractedSkill(
                        skill_id=item.definition.id,
                        surface=match.group(0),
                        evidence_text=text[evidence_start:evidence_end].strip(),
                        requirement_type=requirement_type,
                        start_offset=start,
                        end_offset=end,
                        extraction_confidence=0.96 if required or preferred else 0.90,
                        linking_confidence=0.98 if alias_is_canonical else 0.94,
                    )
                )
                occupied.append((start, end))

        # Keep one strongest mention per skill and requirement type per JD.
        deduplicated: dict[tuple[str, RequirementType], ExtractedSkill] = {}
        for mention in candidates:
            key = (mention.skill_id, mention.requirement_type)
            previous = deduplicated.get(key)
            score = mention.extraction_confidence * mention.linking_confidence
            if previous is None or score > previous.extraction_confidence * previous.linking_confidence:
                deduplicated[key] = mention
        return sorted(deduplicated.values(), key=lambda item: item.start_offset)
