from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.providers.base import ProviderConfig


DEFAULT_DATABASE_URL = "mysql+pymysql://root:hjknmb@127.0.0.1:3306/mog_v2?charset=utf8mb4"
DEFAULT_AUTH_SECRET_KEY = "change-me-in-production"
DEFAULT_DEV_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)
DEFAULT_UPLOAD_CONTENT_TYPES = (
    "image/png",
    "image/jpeg",
    "application/pdf",
    "text/plain",
    "application/octet-stream",
)


class Settings(BaseSettings):
    app_name: str = Field(default="Health Record API", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    database_url: str = Field(
        default=DEFAULT_DATABASE_URL,
        alias="DATABASE_URL",
    )
    auth_secret_key: str = Field(default=DEFAULT_AUTH_SECRET_KEY, alias="AUTH_SECRET_KEY")
    auth_token_expire_minutes: int = Field(default=60, alias="AUTH_TOKEN_EXPIRE_MINUTES")

    ocr_provider: str = Field(default="stub", alias="OCR_PROVIDER")
    ocr_provider_base_url: str | None = Field(default=None, validation_alias=AliasChoices("OCR_BASE_URL", "OCR_PROVIDER_BASE_URL"))
    ocr_provider_model: str | None = Field(default=None, validation_alias=AliasChoices("OCR_MODEL", "OCR_PROVIDER_MODEL"))
    ocr_provider_variant: str | None = Field(default=None, alias="OCR_PROVIDER_VARIANT")
    ocr_provider_api_key: str | None = Field(default=None, validation_alias=AliasChoices("OCR_API_KEY", "OCR_PROVIDER_API_KEY"))
    ocr_provider_secret_ref: str | None = Field(default=None, alias="OCR_PROVIDER_SECRET_REF")
    ocr_provider_timeout_seconds: float = Field(default=30.0, validation_alias=AliasChoices("OCR_TIMEOUT_SECONDS", "OCR_PROVIDER_TIMEOUT_SECONDS"))
    ocr_provider_max_retries: int = Field(default=1, validation_alias=AliasChoices("OCR_MAX_RETRIES", "OCR_PROVIDER_MAX_RETRIES"))
    ocr_max_image_pages: int = Field(default=4, alias="OCR_MAX_IMAGE_PAGES")
    ocr_enable_pdf_fallback: bool = Field(default=False, alias="OCR_ENABLE_PDF_FALLBACK")

    normalization_provider: str = Field(default="rule_based", alias="NORMALIZATION_PROVIDER")
    normalization_provider_base_url: str | None = Field(default=None, alias="NORMALIZATION_PROVIDER_BASE_URL")
    normalization_provider_model: str | None = Field(default=None, alias="NORMALIZATION_PROVIDER_MODEL")
    normalization_provider_variant: str | None = Field(default=None, alias="NORMALIZATION_PROVIDER_VARIANT")
    normalization_provider_api_key: str | None = Field(default=None, alias="NORMALIZATION_PROVIDER_API_KEY")
    normalization_provider_secret_ref: str | None = Field(default=None, alias="NORMALIZATION_PROVIDER_SECRET_REF")
    normalization_provider_timeout_seconds: float = Field(default=120.0, alias="NORMALIZATION_PROVIDER_TIMEOUT_SECONDS")
    normalization_provider_max_retries: int = Field(default=1, alias="NORMALIZATION_PROVIDER_MAX_RETRIES")

    storage_provider: str = Field(default="database_inline", alias="STORAGE_PROVIDER")
    storage_provider_base_url: str | None = Field(default=None, alias="STORAGE_PROVIDER_BASE_URL")
    storage_provider_model: str | None = Field(default=None, alias="STORAGE_PROVIDER_MODEL")
    storage_provider_variant: str | None = Field(default=None, alias="STORAGE_PROVIDER_VARIANT")
    storage_provider_api_key: str | None = Field(default=None, alias="STORAGE_PROVIDER_API_KEY")
    storage_provider_secret_ref: str | None = Field(default=None, alias="STORAGE_PROVIDER_SECRET_REF")
    storage_provider_timeout_seconds: float = Field(default=30.0, alias="STORAGE_PROVIDER_TIMEOUT_SECONDS")
    storage_provider_max_retries: int = Field(default=0, alias="STORAGE_PROVIDER_MAX_RETRIES")

    llm_provider: str = Field(default="stub", alias="LLM_PROVIDER")
    llm_provider_base_url: str | None = Field(default=None, alias="LLM_PROVIDER_BASE_URL")
    llm_provider_model: str | None = Field(default=None, alias="LLM_PROVIDER_MODEL")
    llm_provider_variant: str | None = Field(default=None, alias="LLM_PROVIDER_VARIANT")
    llm_provider_api_key: str | None = Field(default=None, alias="LLM_PROVIDER_API_KEY")
    llm_provider_secret_ref: str | None = Field(default=None, alias="LLM_PROVIDER_SECRET_REF")
    llm_provider_timeout_seconds: float = Field(default=30.0, alias="LLM_PROVIDER_TIMEOUT_SECONDS")
    llm_provider_max_retries: int = Field(default=0, alias="LLM_PROVIDER_MAX_RETRIES")

    is_docs_enabled: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("IS_DOCS_ENABLED", "DOCS_ENABLED"),
    )
    enable_api_test_page: bool | None = Field(default=None, alias="ENABLE_API_TEST_PAGE")
    auto_sync_database_schema: bool | None = Field(default=None, alias="AUTO_SYNC_DATABASE_SCHEMA")
    cors_allow_origins: str = Field(default="", alias="CORS_ALLOW_ORIGINS")
    cors_allow_credentials: bool = Field(default=True, alias="CORS_ALLOW_CREDENTIALS")
    upload_max_bytes: int = Field(default=20 * 1024 * 1024, alias="UPLOAD_MAX_BYTES")
    upload_allowed_content_types: str = Field(
        default=",".join(DEFAULT_UPLOAD_CONTENT_TYPES),
        alias="UPLOAD_ALLOWED_CONTENT_TYPES",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() in {"prod", "production"}

    @property
    def docs_enabled(self) -> bool:
        if self.is_docs_enabled is not None:
            return self.is_docs_enabled
        return not self.is_production

    @property
    def api_test_page_enabled(self) -> bool:
        if self.enable_api_test_page is not None:
            return self.enable_api_test_page
        return not self.is_production

    @property
    def database_schema_sync_enabled(self) -> bool:
        if self.auto_sync_database_schema is not None:
            return self.auto_sync_database_schema
        return not self.is_production

    @property
    def allowed_cors_origins(self) -> list[str]:
        configured = _split_csv(self.cors_allow_origins)
        if configured:
            return configured
        if self.is_production:
            return []
        return list(DEFAULT_DEV_CORS_ORIGINS)

    @property
    def allowed_upload_content_types(self) -> set[str]:
        return set(_split_csv(self.upload_allowed_content_types))

    def validate_runtime_config(self) -> None:
        if self.upload_max_bytes <= 0:
            raise RuntimeError("UPLOAD_MAX_BYTES must be greater than 0")

        allowed_content_types = self.allowed_upload_content_types
        if not allowed_content_types:
            raise RuntimeError("UPLOAD_ALLOWED_CONTENT_TYPES must include at least one content type")

        if not self.is_production:
            return

        if self.auth_secret_key == DEFAULT_AUTH_SECRET_KEY or len(self.auth_secret_key.strip()) < 32:
            raise RuntimeError("AUTH_SECRET_KEY must be set to a strong value in production")
        if self.database_url == DEFAULT_DATABASE_URL or "root:hjknmb@" in self.database_url:
            raise RuntimeError("DATABASE_URL must be set explicitly for production")
        if "*" in self.allowed_cors_origins:
            raise RuntimeError("CORS_ALLOW_ORIGINS cannot contain '*' in production")
        if "*" in allowed_content_types:
            raise RuntimeError("UPLOAD_ALLOWED_CONTENT_TYPES cannot contain '*' in production")

    def provider_matrix(self) -> dict[str, ProviderConfig]:
        return {
            "ocr": ProviderConfig(
                provider_type="ocr",
                name=self.ocr_provider,
                base_url=self.ocr_provider_base_url,
                model=self.ocr_provider_model,
                variant=self.ocr_provider_variant,
                api_key=self.ocr_provider_api_key,
                secret_ref=self.ocr_provider_secret_ref,
                timeout_seconds=self.ocr_provider_timeout_seconds,
                max_retries=self.ocr_provider_max_retries,
                options={
                    "max_image_pages": self.ocr_max_image_pages,
                    "enable_pdf_fallback": self.ocr_enable_pdf_fallback,
                },
            ),
            "normalization": ProviderConfig(
                provider_type="normalization",
                name=self.normalization_provider,
                base_url=self.normalization_provider_base_url,
                model=self.normalization_provider_model,
                variant=self.normalization_provider_variant,
                api_key=self.normalization_provider_api_key,
                secret_ref=self.normalization_provider_secret_ref,
                timeout_seconds=self.normalization_provider_timeout_seconds,
                max_retries=self.normalization_provider_max_retries,
            ),
            "storage": ProviderConfig(
                provider_type="storage",
                name=self.storage_provider,
                base_url=self.storage_provider_base_url,
                model=self.storage_provider_model,
                variant=self.storage_provider_variant,
                api_key=self.storage_provider_api_key,
                secret_ref=self.storage_provider_secret_ref,
                timeout_seconds=self.storage_provider_timeout_seconds,
                max_retries=self.storage_provider_max_retries,
            ),
            "llm": ProviderConfig(
                provider_type="llm",
                name=self.llm_provider,
                base_url=self.llm_provider_base_url,
                model=self.llm_provider_model,
                variant=self.llm_provider_variant,
                api_key=self.llm_provider_api_key,
                secret_ref=self.llm_provider_secret_ref,
                timeout_seconds=self.llm_provider_timeout_seconds,
                max_retries=self.llm_provider_max_retries,
            ),
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]
