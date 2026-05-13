from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.repositories.knowledge_repository import DEFAULT_KNOWLEDGE_CHUNKS
from app.services.knowledge_source_health import build_source_health_report


def main() -> None:
    report = build_source_health_report(DEFAULT_KNOWLEDGE_CHUNKS)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["failed_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
