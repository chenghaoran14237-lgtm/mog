from app.repositories.knowledge_repository import DEFAULT_KNOWLEDGE_CHUNKS
from app.services.knowledge_source_health import build_source_health_report


def test_build_source_health_report_groups_unique_urls_and_counts_status():
    calls: list[str] = []

    def fake_probe(url: str) -> dict:
        calls.append(url)
        return {"ok": "diabetes" in url, "status_code": 200 if "diabetes" in url else 503, "error": None}

    report = build_source_health_report(DEFAULT_KNOWLEDGE_CHUNKS, probe=fake_probe)

    assert report["source_count"] >= 8
    assert report["ok_count"] >= 1
    assert report["failed_count"] >= 1
    assert len(calls) == report["source_count"]
    assert all(item["source_url"].startswith("https://www.msdmanuals.cn/home/") for item in report["sources"])
