from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models.knowledge_chunk import KnowledgeChunk
from app.repositories.knowledge_repository import DEFAULT_KNOWLEDGE_CHUNKS
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.rag_retrieval import rank_knowledge_chunks


def test_lexical_rag_retrieves_glucose_audit_guidance():
    results = rank_knowledge_chunks(
        "空腹血糖 8.2 mmol/L 风险复核 证据绑定",
        DEFAULT_KNOWLEDGE_CHUNKS,
        top_k=3,
    )

    assert results
    assert results[0]["score"] > 0
    assert any("血糖" in item["content"] or "糖代谢" in item["section_title"] for item in results)
    assert {"id", "content", "source_title", "section_title", "score", "matched_terms"} <= set(results[0])


def test_lexical_rag_ranks_alt_liver_context_above_generic_rules():
    results = rank_knowledge_chunks(
        "ALT 66 U/L 肝功能异常 审计建议",
        DEFAULT_KNOWLEDGE_CHUNKS,
        top_k=5,
    )

    assert results
    assert "肝功能" in results[0]["content"] or "ALT" in results[0]["content"]


def test_default_knowledge_contains_source_backed_msd_manual_chunks():
    msd_chunks = [
        item
        for item in DEFAULT_KNOWLEDGE_CHUNKS
        if item.get("metadata_json", {}).get("source_name") == "默沙东诊疗手册大众版"
    ]

    assert len(msd_chunks) >= 8
    assert all(item["metadata_json"]["source_url"].startswith("https://www.msdmanuals.cn/home/") for item in msd_chunks)


def test_rag_retrieves_msd_manual_lipid_context():
    results = rank_knowledge_chunks(
        "LDL-C 4.05 mmol/L 甘油三酯 2.42 mmol/L 血脂异常 审计",
        DEFAULT_KNOWLEDGE_CHUNKS,
        top_k=5,
    )

    assert any(item["metadata_json"].get("source_name") == "默沙东诊疗手册大众版" for item in results)
    assert any("脂" in item["section_title"] or "胆固醇" in item["content"] for item in results)


def test_hybrid_rag_returns_explainable_bm25_breakdown():
    results = rank_knowledge_chunks(
        "ALT AST GGT 肝功能 转氨酶 升高",
        DEFAULT_KNOWLEDGE_CHUNKS,
        top_k=3,
    )

    assert results
    top = results[0]
    assert top["retrieval_method"] == "hybrid_bm25_lexical"
    assert top["score_breakdown"]["bm25"] > 0
    assert top["score_breakdown"]["synonym"] > 0
    assert "肝功能" in top["content"] or "ALT" in top["content"]


def test_knowledge_repository_backfills_new_default_chunks_without_duplicates():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()

    try:
        seed = DEFAULT_KNOWLEDGE_CHUNKS[0]
        session.add(
            KnowledgeChunk(
                scope=seed["scope"],
                source_type=seed["source_type"],
                source_title=seed["source_title"],
                section_title=seed["section_title"],
                content=seed["content"],
                keywords=seed["keywords"],
                tags=seed["tags"],
                metadata_json=seed["metadata_json"],
                is_active=True,
            )
        )
        session.commit()

        repo = KnowledgeRepository(session)
        first = repo.ensure_default_chunks()
        second = repo.ensure_default_chunks()

        assert len(first) == len(DEFAULT_KNOWLEDGE_CHUNKS)
        assert len(second) == len(DEFAULT_KNOWLEDGE_CHUNKS)
        assert sum(1 for item in second if item.metadata_json.get("source_name") == "默沙东诊疗手册大众版") >= 8
    finally:
        session.close()


def test_knowledge_repository_updates_existing_default_chunk_metadata():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()

    try:
        seed = next(item for item in DEFAULT_KNOWLEDGE_CHUNKS if item["id"] == "msd-diabetes-diagnosis")
        stale_payload = dict(seed)
        stale_payload["metadata_json"] = {**seed["metadata_json"], "source_url": "https://example.invalid/stale"}
        session.add(
            KnowledgeChunk(
                scope=stale_payload["scope"],
                source_type=stale_payload["source_type"],
                source_title=stale_payload["source_title"],
                section_title=stale_payload["section_title"],
                content=stale_payload["content"],
                keywords=stale_payload["keywords"],
                tags=stale_payload["tags"],
                metadata_json=stale_payload["metadata_json"],
                is_active=True,
            )
        )
        session.commit()

        chunks = KnowledgeRepository(session).ensure_default_chunks()
        updated = next(item for item in chunks if item.source_title == seed["source_title"])

        assert updated.metadata_json["source_url"] == seed["metadata_json"]["source_url"]
    finally:
        session.close()


def test_knowledge_repository_lists_source_summaries():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()

    try:
        repo = KnowledgeRepository(session)
        repo.ensure_default_chunks()
        summaries = repo.list_source_summaries()

        assert summaries
        assert any(item["source_name"] == "默沙东诊疗手册大众版" for item in summaries)
        assert any(
            item["source_name"] == "默沙东诊疗手册大众版"
            and item["source_url"].startswith("https://www.msdmanuals.cn/home/")
            and item["chunk_count"] >= 1
            and item["sections"]
            for item in summaries
        )
    finally:
        session.close()
