from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.observability import configure_logging, request_context_middleware
from app.core.schema import ensure_database_schema


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        openapi_url="/openapi.json",
        docs_url="/docs" if settings.is_docs_enabled else None,
        redoc_url="/redoc" if settings.is_docs_enabled else None,
    )

    # CORS配置 - 允许前端访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 开发环境允许所有来源
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.middleware("http")(request_context_middleware)
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api")

    @app.on_event("startup")
    def _startup_schema_sync() -> None:
        ensure_database_schema()

    return app


app = create_app()

API_TEST_PAGE = Path(__file__).with_name("api_test.html")


@app.get("/api-test", include_in_schema=False)
def api_test_page() -> FileResponse:
    return FileResponse(API_TEST_PAGE, media_type="text/html; charset=utf-8")
