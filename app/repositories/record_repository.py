from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.record import Record
from app.models.record_file import RecordFile
from app.core.statuses import RecordStatus


class RecordRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_record_by_id(self, record_id: int, user_id: int | None = None) -> Record | None:
        statement = select(Record).where(Record.id == record_id)
        if user_id is not None:
            statement = statement.where(Record.user_id == user_id)
        return self.session.scalar(statement)

    def create_record_with_file(
        self,
        user_id: int,
        original_filename: str,
        content_type: str | None,
        size_bytes: int,
        content_bytes: bytes,
        storage_provider: str | None,
        storage_key: str | None,
        display_name: str | None = None,
    ) -> tuple[Record, RecordFile]:
        record = Record(user_id=user_id, source="upload", status=RecordStatus.UPLOADED)
        self.session.add(record)
        self.session.flush()

        record_file = RecordFile(
            record_id=record.id,
            original_filename=original_filename,
            display_name=display_name,
            content_type=content_type,
            size_bytes=size_bytes,
            content_bytes=content_bytes,
            storage_provider=storage_provider,
            storage_key=storage_key,
        )
        self.session.add(record_file)
        self.session.commit()
        self.session.refresh(record)
        self.session.refresh(record_file)
        return record, record_file

    def get_record_file_by_id(self, record_file_id: int, user_id: int | None = None) -> RecordFile | None:
        statement = (
            select(RecordFile)
            .options(selectinload(RecordFile.record))
            .join(Record, RecordFile.record_id == Record.id)
            .where(RecordFile.id == record_file_id)
        )
        if user_id is not None:
            statement = statement.where(Record.user_id == user_id)
        return self.session.scalar(statement)

    def update_record_status(self, record_id: int, status: str) -> Record:
        record = self.session.get(Record, record_id)
        if record is None:
            raise ValueError("Record not found")
        record.status = status
        self.session.commit()
        self.session.refresh(record)
        return record
