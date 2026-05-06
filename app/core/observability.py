import json
import logging
import time
import uuid

from fastapi import Request

from app.core.request_context import get_request_id, reset_request_id, set_request_id


logger = logging.getLogger("health_record_api")


def configure_logging() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def log_event(event_name: str, **fields: object) -> None:
    payload = {"event": event_name, "request_id": get_request_id(), **fields}
    logger.info(json.dumps(payload, default=str, sort_keys=True))


async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    token = set_request_id(request_id)
    started = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        log_event(
            "http_request",
            method=request.method,
            path=str(request.url.path),
            duration_ms=duration_ms,
        )
        reset_request_id(token)
    if response is not None:
        response.headers["X-Request-ID"] = request_id
    return response
