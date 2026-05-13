from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.db import SessionLocal
from app.repositories.knowledge_repository import KnowledgeRepository


def main() -> None:
    session = SessionLocal()
    try:
        chunks = KnowledgeRepository(session).ensure_default_chunks()
        msd_count = sum(
            1
            for chunk in chunks
            if (chunk.metadata_json or {}).get("source_name") == "默沙东诊疗手册大众版"
        )
        print(f"Seeded RAG knowledge chunks: total={len(chunks)} msd_manual={msd_count}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
