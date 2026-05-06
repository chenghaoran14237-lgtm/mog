from app.providers.base import ProviderConfig, StorageProvider, StorageWriteResult


class DatabaseInlineStorageProvider(StorageProvider):
    def __init__(self, config: ProviderConfig | None = None) -> None:
        super().__init__(config or ProviderConfig(provider_type="storage", name="database_inline"))

    def store(
        self,
        *,
        content_bytes: bytes,
        content_type: str | None,
        original_filename: str,
    ) -> StorageWriteResult:
        return StorageWriteResult(
            provider_name=self.config.name,
            storage_key=None,
            content_bytes=content_bytes,
            metadata={
                "content_type": content_type,
                "original_filename": original_filename,
                "size_bytes": len(content_bytes),
            },
        )
