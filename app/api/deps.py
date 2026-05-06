from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings as _get_settings_core
from app.core.db import get_db_session
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.security import TokenService

bearer_scheme = HTTPBearer(auto_error=False)


def get_settings_dependency() -> Settings:
    return _get_settings_core()


def get_session_dependency(session: Session = Depends(get_db_session)) -> Session:
    return session


# Aliases for backward compatibility
get_session = get_session_dependency
get_settings = get_settings_dependency


def get_token_service_dependency(settings: Settings = Depends(get_settings_dependency)) -> TokenService:
    return TokenService(
        secret_key=settings.auth_secret_key,
        expire_minutes=settings.auth_token_expire_minutes,
    )


def get_current_user_dependency(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_session_dependency),
    token_service: TokenService = Depends(get_token_service_dependency),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = token_service.verify_access_token(credentials.credentials)
    user = UserRepository(session).get_by_id(claims.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# Alias for backward compatibility
get_current_user = get_current_user_dependency

