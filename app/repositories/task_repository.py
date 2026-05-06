from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.task_event import TaskEvent


_MYSQL_STRING_LIMIT = 255


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_task(
        self,
        *,
        user_id: int,
        task_type: str,
        resource_type: str,
        resource_id: int,
        request_id: str | None,
        max_retries: int,
        task_payload: dict | None = None,
        batch_id: str | None = None,
        priority: int = 5,
    ) -> Task:
        task = Task(
            user_id=user_id,
            task_type=task_type,
            resource_type=resource_type,
            resource_id=resource_id,
            status="pending",
            request_id=request_id,
            max_retries=max_retries,
            task_payload=task_payload or {},
            batch_id=batch_id,
            priority=priority,
        )
        self.session.add(task)
        self.session.flush()
        self.create_event(
            task_id=task.id,
            event_type="task_created",
            from_status=None,
            to_status=task.status,
            request_id=request_id,
            message="Task created",
            payload={},
        )
        self.session.commit()
        self.session.refresh(task)
        return task

    def get_by_id(self, task_id: int, *, user_id: int | None = None) -> Task | None:
        statement = select(Task).where(Task.id == task_id)
        if user_id is not None:
            statement = statement.where(Task.user_id == user_id)
        return self.session.scalar(statement)

    def list_tasks(
        self,
        *,
        user_id: int,
        task_type: str | None = None,
        status: str | None = None,
        batch_id: str | None = None,
    ) -> list[Task]:
        statement: Select[tuple[Task]] = select(Task).where(Task.user_id == user_id)
        if task_type is not None:
            statement = statement.where(Task.task_type == task_type)
        if status is not None:
            statement = statement.where(Task.status == status)
        if batch_id is not None:
            statement = statement.where(Task.batch_id == batch_id)
        statement = statement.order_by(Task.priority.desc(), Task.id.asc())
        return list(self.session.scalars(statement).all())

    def list_events(self, task_id: int) -> list[TaskEvent]:
        statement = select(TaskEvent).where(TaskEvent.task_id == task_id).order_by(TaskEvent.id.asc())
        return list(self.session.scalars(statement).all())

    def find_active_task(
        self,
        *,
        user_id: int,
        task_type: str,
        resource_type: str,
        resource_id: int,
    ) -> Task | None:
        statement = (
            select(Task)
            .where(Task.user_id == user_id)
            .where(Task.task_type == task_type)
            .where(Task.resource_type == resource_type)
            .where(Task.resource_id == resource_id)
            .where(Task.status.in_(["pending", "processing"]))
            .order_by(Task.id.desc())
        )
        return self.session.scalar(statement)

    def find_latest_terminal_task(
        self,
        *,
        user_id: int,
        task_type: str,
        resource_type: str,
        resource_id: int,
    ) -> Task | None:
        statement = (
            select(Task)
            .where(Task.user_id == user_id)
            .where(Task.task_type == task_type)
            .where(Task.resource_type == resource_type)
            .where(Task.resource_id == resource_id)
            .where(Task.status.in_(["completed", "failed"]))
            .order_by(Task.id.desc())
        )
        return self.session.scalar(statement)

    def mark_processing(self, task_id: int, *, request_id: str | None = None) -> Task:
        task = self._require_task(task_id)
        previous_status = task.status
        task.status = "processing"
        task.started_at = datetime.now(UTC)
        task.attempt_count += 1
        task.request_id = request_id or task.request_id
        self.create_event(
            task_id=task.id,
            event_type="task_processing",
            from_status=previous_status,
            to_status=task.status,
            request_id=task.request_id,
            message="Task processing started",
            payload={"attempt_count": task.attempt_count},
        )
        self.session.commit()
        self.session.refresh(task)
        return task

    def mark_completed(
        self,
        task_id: int,
        *,
        result_resource_type: str,
        result_resource_id: int,
        request_id: str | None = None,
    ) -> Task:
        task = self._require_task(task_id)
        previous_status = task.status
        task.status = "completed"
        task.completed_at = datetime.now(UTC)
        task.result_resource_type = result_resource_type
        task.result_resource_id = result_resource_id
        task.last_error_category = None
        task.last_error_code = None
        task.last_error_message = None
        task.last_error_retryable = False
        task.request_id = request_id or task.request_id
        self.create_event(
            task_id=task.id,
            event_type="task_completed",
            from_status=previous_status,
            to_status=task.status,
            request_id=task.request_id,
            message="Task completed",
            payload={
                "result_resource_type": result_resource_type,
                "result_resource_id": result_resource_id,
            },
        )
        self.session.commit()
        self.session.refresh(task)
        return task

    def mark_failed(
        self,
        task_id: int,
        *,
        error_category: str,
        error_code: str,
        error_message: str,
        retryable: bool,
        request_id: str | None = None,
    ) -> Task:
        task = self._require_task(task_id)
        previous_status = task.status
        task.status = "failed"
        task.completed_at = datetime.now(UTC)
        task.last_error_category = error_category
        task.last_error_code = error_code
        task.last_error_message = self._safe_message(error_message)
        task.last_error_retryable = retryable
        task.request_id = request_id or task.request_id
        self.create_event(
            task_id=task.id,
            event_type="task_failed",
            from_status=previous_status,
            to_status=task.status,
            request_id=task.request_id,
            message=self._safe_message(error_message),
            payload={
                "error_category": error_category,
                "error_code": error_code,
                "full_error_message": error_message,
                "retryable": retryable,
            },
        )
        self.session.commit()
        self.session.refresh(task)
        return task

    def schedule_retry(
        self,
        task_id: int,
        *,
        error_category: str,
        error_code: str,
        error_message: str,
        request_id: str | None = None,
    ) -> Task:
        task = self._require_task(task_id)
        previous_status = task.status
        task.status = "pending"
        task.last_error_category = error_category
        task.last_error_code = error_code
        task.last_error_message = self._safe_message(error_message)
        task.last_error_retryable = True
        task.request_id = request_id or task.request_id
        self.create_event(
            task_id=task.id,
            event_type="task_retry_scheduled",
            from_status=previous_status,
            to_status=task.status,
            request_id=task.request_id,
            message=self._safe_message(error_message),
            payload={
                "error_category": error_category,
                "error_code": error_code,
                "full_error_message": error_message,
                "attempt_count": task.attempt_count,
            },
        )
        self.session.commit()
        self.session.refresh(task)
        return task

    def reset_for_retry(self, task_id: int, *, request_id: str | None = None) -> Task:
        task = self._require_task(task_id)
        previous_status = task.status
        task.status = "pending"
        task.completed_at = None
        task.started_at = None
        task.last_error_category = None
        task.last_error_code = None
        task.last_error_message = None
        task.last_error_retryable = False
        task.request_id = request_id or task.request_id
        self.create_event(
            task_id=task.id,
            event_type="task_retried",
            from_status=previous_status,
            to_status=task.status,
            request_id=task.request_id,
            message="Task queued for retry",
            payload={"attempt_count": task.attempt_count},
        )
        self.session.commit()
        self.session.refresh(task)
        return task

    def create_event(
        self,
        *,
        task_id: int,
        event_type: str,
        from_status: str | None,
        to_status: str | None,
        request_id: str | None,
        message: str | None,
        payload: dict,
    ) -> TaskEvent:
        event = TaskEvent(
            task_id=task_id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            request_id=request_id,
            message=self._safe_message(message),
            payload=payload,
        )
        self.session.add(event)
        self.session.flush()
        return event

    def _require_task(self, task_id: int) -> Task:
        task = self.session.get(Task, task_id)
        if task is None:
            raise ValueError("Task not found")
        return task

    @staticmethod
    def _safe_message(message: str | None) -> str | None:
        if message is None:
            return None
        text = str(message)
        if len(text) <= _MYSQL_STRING_LIMIT:
            return text
        suffix = "...[truncated]"
        return f"{text[: _MYSQL_STRING_LIMIT - len(suffix)]}{suffix}"
