from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

import httpx


Probe = Callable[[str], dict[str, Any]]


def build_source_health_report(chunks: Iterable[dict[str, Any]], *, probe: Probe | None = None) -> dict[str, Any]:
    probe_source = probe or probe_source_url
    sources = _unique_sources(chunks)
    checked_sources: list[dict[str, Any]] = []
    for source in sources:
        result = probe_source(source["source_url"])
        checked_sources.append({**source, **result})

    ok_count = sum(1 for item in checked_sources if item.get("ok"))
    return {
        "source_count": len(checked_sources),
        "ok_count": ok_count,
        "failed_count": len(checked_sources) - ok_count,
        "sources": checked_sources,
    }


def probe_source_url(url: str, *, timeout: float = 8.0) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": "mog-rag-source-check/1.0"})
        return {
            "ok": 200 <= response.status_code < 400,
            "status_code": response.status_code,
            "final_url": str(response.url),
            "error": None,
        }
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "status_code": None,
            "final_url": url,
            "error": str(exc),
        }


def _unique_sources(chunks: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        metadata = chunk.get("metadata_json") or {}
        source_url = metadata.get("source_url")
        if not source_url:
            continue
        source = sources.setdefault(
            source_url,
            {
                "source_name": metadata.get("source_name") or chunk.get("source_title"),
                "source_title": chunk.get("source_title"),
                "source_url": source_url,
                "source_type": chunk.get("source_type"),
                "sections": [],
            },
        )
        section_title = chunk.get("section_title")
        if section_title and section_title not in source["sections"]:
            source["sections"].append(section_title)
    return list(sources.values())
