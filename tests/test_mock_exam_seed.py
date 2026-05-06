from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models import ExtractedDocument, Measurement, Record, User
from scripts.seed_mock_exam_data import MOCK_EMAIL, MOCK_PASSWORD, MOCK_SOURCE, seed_mock_exam_data


def test_seed_mock_exam_data_creates_account_and_rich_medical_dataset():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()

    summary = seed_mock_exam_data(session, reset=True)

    user = session.scalar(select(User).where(User.email == MOCK_EMAIL))
    document_count = session.scalar(
        select(func.count(ExtractedDocument.id))
        .join(Record, ExtractedDocument.record_id == Record.id)
        .where(Record.user_id == user.id, Record.source == MOCK_SOURCE)
    )
    measurement_count = session.scalar(
        select(func.count(Measurement.id))
        .join(ExtractedDocument, Measurement.extracted_document_id == ExtractedDocument.id)
        .join(Record, ExtractedDocument.record_id == Record.id)
        .where(Record.user_id == user.id, Record.source == MOCK_SOURCE)
    )
    categories = set(
        session.scalars(
            select(ExtractedDocument.document_category)
            .join(Record, ExtractedDocument.record_id == Record.id)
            .where(Record.user_id == user.id, Record.source == MOCK_SOURCE)
        ).all()
    )

    assert user is not None
    assert MOCK_PASSWORD == "Exam@123456"
    assert summary["document_count"] >= 12
    assert summary["measurement_count"] >= 60
    assert document_count == summary["document_count"]
    assert measurement_count == summary["measurement_count"]
    assert categories == {"structured_metrics", "narrative_context"}


def test_seed_mock_exam_data_is_idempotent_without_reset():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()

    first = seed_mock_exam_data(session, reset=True)
    second = seed_mock_exam_data(session, reset=False)

    assert second["document_count"] == first["document_count"]
    assert second["measurement_count"] == first["measurement_count"]
