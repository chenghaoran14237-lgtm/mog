from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.db import SessionLocal
from app.core.schema import ensure_database_schema
from app.models import DocumentVersion, ExtractedDocument, Measurement, Record, User, UserProfile
from app.services.security import PasswordHasher
from scripts.seed_admin_mock_data import ADMIN_SOURCE, _delete_existing_admin_mock_data
from scripts.seed_handtest_medical_data import (
    HANDTEST_SOURCE,
    _create_document,
    _delete_existing_handtest_data,
    build_mock_documents,
)

DEMO_EMAIL = "admin@qq.com"
DEMO_PASSWORD = "123123123"


def seed_online_demo_data(session: Session, *, reset: bool = True) -> dict:
    user = _upsert_demo_user(session)

    if reset:
        _delete_existing_admin_mock_data(session, user_id=user.id)
        _delete_existing_handtest_data(session, user_id=user.id)

    existing_count = _online_document_count(session, user_id=user.id)
    if not existing_count:
        for spec in build_mock_documents():
            _create_document(session, user_id=user.id, spec=spec)

    session.commit()
    return _summary(session, user_id=user.id)


def _upsert_demo_user(session: Session) -> User:
    user = session.scalar(select(User).where(User.email == DEMO_EMAIL))
    password_hash = PasswordHasher().hash_password(DEMO_PASSWORD)
    if user is None:
        user = User(email=DEMO_EMAIL, password_hash=password_hash)
        session.add(user)
        session.flush()
    else:
        user.password_hash = password_hash
        session.flush()

    profile = session.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    if profile is None:
        session.add(
            UserProfile(
                user_id=user.id,
                display_name="线上演示账号",
                preferences={"mock_dataset": HANDTEST_SOURCE, "scenario": "metabolic_audit"},
            )
        )
    else:
        profile.display_name = "线上演示账号"
        profile.preferences = {"mock_dataset": HANDTEST_SOURCE, "scenario": "metabolic_audit"}
    session.flush()
    return user


def _online_document_count(session: Session, *, user_id: int) -> int:
    return int(
        session.scalar(
            select(func.count(ExtractedDocument.id))
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(Record.user_id == user_id, Record.source == HANDTEST_SOURCE)
        )
        or 0
    )


def _summary(session: Session, *, user_id: int) -> dict:
    source_names = (ADMIN_SOURCE, HANDTEST_SOURCE)
    document_count = int(
        session.scalar(
            select(func.count(ExtractedDocument.id))
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(Record.user_id == user_id, Record.source.in_(source_names))
        )
        or 0
    )
    measurement_count = int(
        session.scalar(
            select(func.count(Measurement.id))
            .join(ExtractedDocument, Measurement.extracted_document_id == ExtractedDocument.id)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(Record.user_id == user_id, Record.source.in_(source_names))
        )
        or 0
    )
    version_ids = list(
        session.scalars(
            select(DocumentVersion.id)
            .join(ExtractedDocument, DocumentVersion.document_id == ExtractedDocument.id)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(Record.user_id == user_id, Record.source.in_(source_names))
            .order_by(DocumentVersion.report_date.asc(), DocumentVersion.id.asc())
        ).all()
    )
    category_rows = session.execute(
        select(ExtractedDocument.document_category, func.count(ExtractedDocument.id))
        .join(Record, ExtractedDocument.record_id == Record.id)
        .where(Record.user_id == user_id, Record.source.in_(source_names))
        .group_by(ExtractedDocument.document_category)
    ).all()
    return {
        "email": DEMO_EMAIL,
        "password": DEMO_PASSWORD,
        "sources": list(source_names),
        "document_count": document_count,
        "measurement_count": measurement_count,
        "document_version_ids": version_ids,
        "categories": {name: count for name, count in category_rows},
    }


def main() -> None:
    ensure_database_schema()
    session = SessionLocal()
    try:
        summary = seed_online_demo_data(session, reset=True)
        print(
            "Seeded online demo data: "
            f"email={summary['email']} password={summary['password']} "
            f"documents={summary['document_count']} measurements={summary['measurement_count']} "
            f"categories={summary['categories']}"
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
