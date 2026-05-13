import pytest

from app.core.config import DEFAULT_AUTH_SECRET_KEY, DEFAULT_DATABASE_URL, Settings


def test_development_defaults_keep_demo_features_enabled():
    settings = Settings(app_env="development")

    assert settings.docs_enabled is True
    assert settings.api_test_page_enabled is True
    assert settings.database_schema_sync_enabled is True
    assert "http://localhost:5173" in settings.allowed_cors_origins


def test_production_rejects_demo_secret_and_database_url():
    settings = Settings(
        app_env="production",
        database_url=DEFAULT_DATABASE_URL,
        auth_secret_key=DEFAULT_AUTH_SECRET_KEY,
    )

    with pytest.raises(RuntimeError, match="AUTH_SECRET_KEY"):
        settings.validate_runtime_config()


def test_production_defaults_disable_demo_endpoints_and_schema_sync():
    settings = Settings(
        app_env="production",
        database_url="mysql+pymysql://mog:secret@db:3306/mog?charset=utf8mb4",
        auth_secret_key="x" * 40,
    )

    settings.validate_runtime_config()

    assert settings.docs_enabled is False
    assert settings.api_test_page_enabled is False
    assert settings.database_schema_sync_enabled is False
    assert settings.allowed_cors_origins == []
