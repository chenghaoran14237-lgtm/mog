class ProviderError(Exception):
    def __init__(
        self,
        *,
        provider_type: str,
        provider_name: str,
        category: str,
        code: str,
        message: str,
        retryable: bool,
        details: dict | None = None,
    ) -> None:
        self.provider_type = provider_type
        self.provider_name = provider_name
        self.category = category
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}
        super().__init__(message)


class ProviderConfigurationError(ProviderError):
    def __init__(self, *, provider_type: str, provider_name: str, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(
            provider_type=provider_type,
            provider_name=provider_name,
            category="configuration_error",
            code=code,
            message=message,
            retryable=False,
            details=details,
        )


class ProviderRetryableError(ProviderError):
    def __init__(self, *, provider_type: str, provider_name: str, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(
            provider_type=provider_type,
            provider_name=provider_name,
            category="retryable_error",
            code=code,
            message=message,
            retryable=True,
            details=details,
        )


class ProviderNonRetryableError(ProviderError):
    def __init__(self, *, provider_type: str, provider_name: str, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(
            provider_type=provider_type,
            provider_name=provider_name,
            category="non_retryable_error",
            code=code,
            message=message,
            retryable=False,
            details=details,
        )


class ProviderExternalServiceError(ProviderError):
    def __init__(
        self,
        *,
        provider_type: str,
        provider_name: str,
        code: str,
        message: str,
        retryable: bool,
        details: dict | None = None,
    ) -> None:
        super().__init__(
            provider_type=provider_type,
            provider_name=provider_name,
            category="external_service_error",
            code=code,
            message=message,
            retryable=retryable,
            details=details,
        )
