from fastapi import HTTPException, status

from app.core.config import Settings
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthTokenResponse, RegisterResponse, UserLoginRequest, UserRegisterRequest, UserResponse
from app.services.security import PasswordHasher, TokenService


class AuthService:
    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
        token_service: TokenService,
    ) -> None:
        self.user_repository = user_repository
        self.password_hasher = password_hasher
        self.token_service = token_service

    @classmethod
    def from_settings(cls, user_repository: UserRepository, settings: Settings) -> "AuthService":
        return cls(
            user_repository=user_repository,
            password_hasher=PasswordHasher(),
            token_service=TokenService(
                secret_key=settings.auth_secret_key,
                expire_minutes=settings.auth_token_expire_minutes,
            ),
        )

    def register(self, payload: UserRegisterRequest) -> RegisterResponse:
        existing_user = self.user_repository.get_by_email(payload.email)
        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        user = self.user_repository.create(
            email=payload.email,
            password_hash=self.password_hasher.hash_password(payload.password),
        )
        return RegisterResponse(user=UserResponse.model_validate(user))

    def login(self, payload: UserLoginRequest) -> AuthTokenResponse:
        user = self.user_repository.get_by_email(payload.email)
        if user is None or not self.password_hasher.verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        return AuthTokenResponse(
            access_token=self.token_service.issue_access_token(user_id=user.id, email=user.email),
        )
