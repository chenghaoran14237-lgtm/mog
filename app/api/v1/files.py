from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_dependency, get_session_dependency, get_settings_dependency
from app.core.config import Settings
from app.models.user import User
from app.providers.registry import ProviderRegistry
from app.repositories.provider_event_repository import ProviderEventRepository
from app.repositories.record_repository import RecordRepository
from app.schemas.file_upload import FileUploadResponse
from app.services.file_upload_service import FileUploadService
from app.services.provider_gateway import ProviderGateway

router = APIRouter(prefix="/files")


@router.post("/upload", response_model=FileUploadResponse, status_code=201)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    display_name: str = Form(..., description="用户自定义的文件显示名称"),
    current_user: User = Depends(get_current_user_dependency),
    settings: Settings = Depends(get_settings_dependency),
    session: Session = Depends(get_session_dependency),
) -> FileUploadResponse:
    content_type = (file.content_type or "application/octet-stream").split(";", maxsplit=1)[0].lower().strip()
    allowed_content_types = settings.allowed_upload_content_types
    if "*" not in allowed_content_types and content_type not in allowed_content_types:
        await file.close()
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {content_type}",
        )

    chunks: list[bytes] = []
    size_bytes = 0
    while chunk := await file.read(1024 * 1024):
        size_bytes += len(chunk)
        if size_bytes > settings.upload_max_bytes:
            await file.close()
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Uploaded file is too large. Maximum allowed size is {settings.upload_max_bytes} bytes",
            )
        chunks.append(chunk)
    await file.close()
    contents = b"".join(chunks)
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    if not display_name or not display_name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Display name is required")

    service = FileUploadService(
        RecordRepository(session),
        ProviderGateway(
            provider_registry=ProviderRegistry(),
            provider_event_repository=ProviderEventRepository(session),
        ),
    )
    return service.create_upload(
        user_id=current_user.id,
        request_id=getattr(request.state, "request_id", None),
        original_filename=file.filename or "uploaded.bin",
        content_type=content_type,
        size_bytes=size_bytes,
        content_bytes=contents,
        display_name=display_name.strip(),
    )
