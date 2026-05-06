from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.providers.base import ProviderConfig


class Settings(BaseSettings):
    app_name: str = Field(default="Health Record API", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    database_url: str = Field(
        default="mysql+pymysql://root:hjknmb@127.0.0.1:3306/mog_v2?charset=utf8mb4",
        alias="DATABASE_URL",
    )
    auth_secret_key: str = Field(default="change-me-in-production", alias="AUTH_SECRET_KEY")
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

    is_docs_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

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
