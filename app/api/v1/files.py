from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_dependency, get_session_dependency
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
    session: Session = Depends(get_session_dependency),
) -> FileUploadResponse:
    contents = await file.read()
    await file.close()
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
        content_type=file.content_type,
        size_bytes=len(contents),
        content_bytes=contents,
        display_name=display_name.strip(),
    )
