from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.provider_event import ProviderEvent


class ProviderEventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_event(
        self,
        *,
        task_id: int | None,
        user_id: int | None,
        provider_type: str,
        provider_name: str,
        operation: str,
        resource_type: str,
        resource_id: int,
        status: str,
        error_category: str | None,
        error_code: str | None,
        retryable: bool,
        duration_ms: int | None,
        request_id: str | None,
        payload: dict,
    ) -> ProviderEvent:
        event = ProviderEvent(
            task_id=task_id,
            user_id=user_id,
            provider_type=provider_type,
            provider_name=provider_name,
            operation=operation,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            error_category=error_category,
            error_code=error_code,
            retryable=retryable,
            duration_ms=duration_ms,
            request_id=request_id,
            payload=payload,
        )
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event

    def list_for_task(self, task_id: int) -> list[ProviderEvent]:
        statement = select(ProviderEvent).where(ProviderEvent.task_id == task_id).order_by(ProviderEvent.id.asc())
        return list(self.session.scalars(statement).all())
