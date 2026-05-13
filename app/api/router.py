from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.audit_reports import router as audit_reports_router
from app.api.v1.chat import router as chat_router
from app.api.v1.files import router as files_router
from app.api.v1.health import router as health_router
from app.api.v1.ingestion import router as ingestion_router
from app.api.v1.insight import router as insight_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.ocr import router as ocr_router
from app.api.v1.query import router as query_router
from app.api.v1.tasks import router as tasks_router

api_router = APIRouter()
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(audit_reports_router)
api_router.include_router(chat_router, tags=["chat"])
api_router.include_router(files_router, tags=["files"])
api_router.include_router(health_router, tags=["health"])
api_router.include_router(ingestion_router, tags=["ingestion"])
api_router.include_router(insight_router, tags=["insight"])
api_router.include_router(knowledge_router)
api_router.include_router(ocr_router, tags=["ocr"])
api_router.include_router(query_router, tags=["query"])
api_router.include_router(tasks_router, tags=["tasks"])
