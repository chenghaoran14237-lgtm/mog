from __future__ import annotations

from app.models.user import User
from app.modules.factories import build_auth_service
from app.schemas.auth import AuthTokenResponse, RegisterResponse, UserLoginRequest, UserRegisterRequest, UserResponse


class UserModuleAPI:
    def __init__(self, auth_service) -> None:
        self.auth_service = auth_service

    def register(self, payload: UserRegisterRequest) -> RegisterResponse:
        return self.auth_service.register(payload)

    def login(self, payload: UserLoginRequest) -> AuthTokenResponse:
        return self.auth_service.login(payload)

    def get_current_user(self, current_user: User) -> UserResponse:
        return UserResponse.model_validate(current_user)

    @classmethod
    def from_session(cls, session, settings) -> "UserModuleAPI":
        return cls(build_auth_service(session, settings))
