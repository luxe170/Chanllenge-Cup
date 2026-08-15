from app.catalog import load_catalog
from app.catalog_store import load_runtime_catalog
from app.database import Base, build_engine
from app.domain import RequirementType
from app.extraction import CatalogExtractor, normalize_title
from sqlalchemy.orm import sessionmaker


def test_title_normalization_and_position_linking():
    extractor = CatalogExtractor(load_catalog())
    linked = extractor.link_position("高级 AI Agent 研发工程师（北京）")
    assert linked.position_id == "pos_ai_agent_engineer"
    assert linked.status == "linked"
    assert "北京" not in normalize_title("高级 AI Agent 研发工程师（北京）")


def test_skill_extraction_is_evidence_backed_and_deduplicated():
    extractor = CatalogExtractor(load_catalog())
    mentions = extractor.extract_skills(
        "AI Agent 研发工程师",
        "研发",
        "负责基于 Python 和 RAG 构建智能体应用。",
        "要求熟练掌握 Python；有 LangChain 项目经验者优先。",
    )
    ids = {item.skill_id for item in mentions}
    assert {"skill_python", "skill_rag", "skill_agent", "skill_langchain"} <= ids
    assert all(item.evidence_text for item in mentions)
    assert all(item.end_offset > item.start_offset for item in mentions)
    langchain = next(item for item in mentions if item.skill_id == "skill_langchain")
    assert langchain.requirement_type == RequirementType.PREFERRED


def test_unknown_position_becomes_review_candidate():
    linked = CatalogExtractor(load_catalog()).link_position("量子工作流编排师")
    assert linked.status == "pending"
    assert linked.position_id.startswith("candidate_")


def test_department_suffix_does_not_fragment_position_candidates():
    assert normalize_title("多模态模型部署优化工程师-Data") == "多模态模型部署优化工程师"


def test_first_runtime_catalog_load_includes_seeded_aliases(tmp_path):
    engine = build_engine(f"sqlite:///{(tmp_path / 'catalog.db').as_posix()}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with sessions() as session:
        extractor = CatalogExtractor(load_runtime_catalog(session))
        mentions = extractor.extract_skills("", "", "", "要求掌握大模型、图像识别与 Spark。")

    assert {"skill_llm", "skill_computer_vision", "skill_spark"} <= {
        mention.skill_id for mention in mentions
    }
