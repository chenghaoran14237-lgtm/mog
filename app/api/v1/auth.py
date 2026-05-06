from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_dependency, get_session_dependency, get_settings_dependency
from app.core.config import Settings
from app.models.user import User
from app.modules.user_api import UserModuleAPI
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthTokenResponse, RegisterResponse, UserLoginRequest, UserRegisterRequest, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth")


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(
    payload: UserRegisterRequest,
    session: Session = Depends(get_session_dependency),
    settings: Settings = Depends(get_settings_dependency),
) -> RegisterResponse:
    service = AuthService.from_settings(UserRepository(session), settings)
    return service.register(payload)


@router.post("/login", response_model=AuthTokenResponse)
def login(
    payload: UserLoginRequest,
    session: Session = Depends(get_session_dependency),
    settings: Settings = Depends(get_settings_dependency),
) -> AuthTokenResponse:
    service = AuthService.from_settings(UserRepository(session), settings)
    return service.login(payload)


@router.get("/me", response_model=UserResponse)
def get_current_user(
    current_user: User = Depends(get_current_user_dependency),
    session: Session = Depends(get_session_dependency),
    settings: Settings = Depends(get_settings_dependency),
) -> UserResponse:
    api = UserModuleAPI.from_session(session, settings)
    return api.get_current_user(current_user)
