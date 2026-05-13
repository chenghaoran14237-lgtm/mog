from __future__ import annotations

import re
from collections.abc import Iterable
from math import log
from typing import Any


_DOMAIN_SYNONYMS = {
    "糖": {"血糖", "空腹血糖", "glucose", "hba1c", "糖代谢", "糖尿病"},
    "肝": {"肝功能", "alt", "ast", "谷丙", "转氨酶"},
    "炎": {"crp", "c反应", "白细胞", "wbc", "感染", "炎症"},
    "证": {"证据", "引用", "追溯", "原文", "measurements", "raw_text"},
    "审": {"审计", "合规", "质量", "风险", "复核"},
    "压": {"血压", "高血压", "收缩压", "舒张压", "mmhg", "hypertension"},
    "脂": {"血脂", "胆固醇", "ldl", "ldl-c", "hdl", "甘油三酯", "tg", "triglyceride"},
    "尿": {"尿酸", "痛风", "gout", "uric"},
    "肾": {"肾功能", "肌酐", "egfr", "bun", "尿素氮", "creatinine"},
    "甲": {"甲状腺", "tsh", "t3", "t4"},
}


def rank_knowledge_chunks(query: str, chunks: Iterable[Any], top_k: int = 5) -> list[dict[str, Any]]:
    """Rank knowledge chunks with deterministic lexical scoring.

    The project currently needs a stable local RAG path for audit demos. This
    scorer is intentionally transparent: token overlap, exact keyword hits and
    domain synonym hits determine the returned context.
    """

    chunk_payloads = [_chunk_to_dict(chunk) for chunk in chunks]
    corpus_terms = [_weighted_terms(payload) for payload in chunk_payloads]
    query_terms = _tokens(query)
    query_text = query.lower()
    avg_doc_len = sum(len(terms) for terms in corpus_terms) / max(1, len(corpus_terms))
    document_frequency = _document_frequency(corpus_terms)
    scored: list[dict[str, Any]] = []
    for payload, weighted_terms in zip(chunk_payloads, corpus_terms, strict=False):
        haystack = _haystack(payload).lower()
        chunk_terms = set(weighted_terms)
        matched_terms = sorted(query_terms & chunk_terms)
        overlap_score = float(len(matched_terms))
        keyword_score = 0.0
        synonym_score = 0.0
        bm25_score = _bm25_score(
            query_terms=query_terms,
            document_terms=weighted_terms,
            document_frequency=document_frequency,
            document_count=len(corpus_terms),
            avg_doc_len=avg_doc_len,
        )

        for keyword in payload.get("keywords") or []:
            keyword_text = str(keyword).lower()
            if keyword_text and keyword_text in query_text:
                matched_terms.append(keyword_text)
                keyword_score += 3.0

        for anchor, synonyms in _DOMAIN_SYNONYMS.items():
            query_hit = any(term.lower() in query_text for term in synonyms) or anchor in query_text
            chunk_hit = any(term.lower() in haystack for term in synonyms) or anchor in haystack
            if query_hit and chunk_hit:
                synonym_score += 2.5
                matched_terms.append(anchor)

        score = bm25_score + keyword_score + synonym_score + overlap_score
        if score <= 0:
            continue
        scored.append(
            {
                **payload,
                "score": round(score, 3),
                "retrieval_method": "hybrid_bm25_lexical",
                "score_breakdown": {
                    "bm25": round(bm25_score, 3),
                    "keyword": round(keyword_score, 3),
                    "synonym": round(synonym_score, 3),
                    "overlap": round(overlap_score, 3),
                },
                "matched_terms": sorted(set(matched_terms))[:16],
            }
        )

    scored.sort(key=lambda item: (item["score"], str(item.get("source_title") or "")), reverse=True)
    return scored[: max(1, int(top_k))]


def _weighted_terms(payload: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    terms.extend(_tokens(str(payload.get("source_title") or "")))
    terms.extend(_repeat_terms(_tokens(str(payload.get("section_title") or "")), 2))
    terms.extend(_tokens(str(payload.get("content") or "")))
    for keyword in payload.get("keywords") or []:
        terms.extend(_repeat_terms(_tokens(str(keyword)), 3))
    for tag in payload.get("tags") or []:
        terms.extend(_tokens(str(tag)))
    return [term for term in terms if term]


def _repeat_terms(terms: set[str], times: int) -> list[str]:
    repeated: list[str] = []
    for _ in range(times):
        repeated.extend(terms)
    return repeated


def _haystack(payload: dict[str, Any]) -> str:
    return " ".join(
        [
            str(payload.get("source_title") or ""),
            str(payload.get("section_title") or ""),
            str(payload.get("content") or ""),
            " ".join(str(item) for item in payload.get("keywords") or []),
            " ".join(str(item) for item in payload.get("tags") or []),
        ]
    )


def _document_frequency(corpus_terms: list[list[str]]) -> dict[str, int]:
    frequency: dict[str, int] = {}
    for terms in corpus_terms:
        for term in set(terms):
            frequency[term] = frequency.get(term, 0) + 1
    return frequency


def _bm25_score(
    *,
    query_terms: set[str],
    document_terms: list[str],
    document_frequency: dict[str, int],
    document_count: int,
    avg_doc_len: float,
) -> float:
    if not query_terms or not document_terms:
        return 0.0
    k1 = 1.5
    b = 0.75
    doc_len = len(document_terms)
    term_frequency: dict[str, int] = {}
    for term in document_terms:
        term_frequency[term] = term_frequency.get(term, 0) + 1

    score = 0.0
    for term in query_terms:
        tf = term_frequency.get(term, 0)
        if tf == 0:
            continue
        df = document_frequency.get(term, 0)
        idf = log(1 + (document_count - df + 0.5) / (df + 0.5))
        denominator = tf + k1 * (1 - b + b * doc_len / max(avg_doc_len, 1e-9))
        score += idf * (tf * (k1 + 1)) / denominator
    return score


def _chunk_to_dict(chunk: Any) -> dict[str, Any]:
    if isinstance(chunk, dict):
        return {
            "id": chunk.get("id"),
            "scope": chunk.get("scope") or "medical_audit",
            "source_type": chunk.get("source_type") or "audit_rule",
            "source_title": chunk.get("source_title") or "",
            "section_title": chunk.get("section_title") or "",
            "content": chunk.get("content") or "",
            "keywords": list(chunk.get("keywords") or []),
            "tags": list(chunk.get("tags") or []),
            "metadata_json": dict(chunk.get("metadata_json") or chunk.get("metadata") or {}),
        }
    return {
        "id": getattr(chunk, "id", None),
        "scope": getattr(chunk, "scope", "medical_audit"),
        "source_type": getattr(chunk, "source_type", "audit_rule"),
        "source_title": getattr(chunk, "source_title", ""),
        "section_title": getattr(chunk, "section_title", ""),
        "content": getattr(chunk, "content", ""),
        "keywords": list(getattr(chunk, "keywords", None) or []),
        "tags": list(getattr(chunk, "tags", None) or []),
        "metadata_json": dict(getattr(chunk, "metadata_json", None) or {}),
    }


def _tokens(text: str) -> set[str]:
    normalized = text.lower()
    tokens = set(re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", normalized))
    cjk_runs = re.findall(r"[\u4e00-\u9fff]+", normalized)
    for run in cjk_runs:
        tokens.update(run)
        tokens.update(run[index : index + 2] for index in range(max(0, len(run) - 1)))
        tokens.update(run[index : index + 3] for index in range(max(0, len(run) - 2)))
        for char in run:
            if char.strip():
                tokens.add(char)
    return {token for token in tokens if token}
