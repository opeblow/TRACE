from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "TRACE API"
    TRACE_ENV: str = ""
    TATUM_MAINNET_API_KEY: str = ""
    TATUM_GRPC_TARGET: str = "sui-mainnet-grpc.gateway.tatum.io:443"
    REDIS_URL: str = ""
    # "redis" (shared, multi-instance) or "memory" (single-instance deployments only)
    RATE_LIMIT_STORE: str = Field(default="redis", pattern=r"^(redis|memory)$")
    ANALYSIS_RATE_LIMIT: int = Field(default=10, ge=1, le=1000)
    ANALYSIS_RATE_WINDOW_SECONDS: int = Field(default=60, ge=1, le=3600)
    WALRUS_MEMORY_PRIVATE_KEY: str = ""
    WALRUS_MEMORY_PUBLIC_KEY: str = ""
    MEMWAL_ACCOUNT_ID: str = ""
    MEMWAL_SERVER_URL: str = "https://relayer.memory.walrus.xyz"
    MEMWAL_NAMESPACE_PREFIX: str = Field(default="trace-dev", pattern=r"^[a-z0-9][a-z0-9-]{1,40}$")
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000"
    ALLOWED_HOSTS: str = "localhost,127.0.0.1,testserver,*.onrender.com"

    ENABLE_API_DOCS: bool = False
    LOG_FORMAT: str = Field(default="auto", pattern=r"^(auto|json|text)$")

    @property
    def env(self) -> str:
        return self.TRACE_ENV.strip().lower()

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def memory_configured(self) -> bool:
        return bool(self.WALRUS_MEMORY_PRIVATE_KEY and self.MEMWAL_ACCOUNT_ID)

    def configuration_problems(self) -> list[str]:
        """Names what is missing or unsafe for production. Never includes values."""
        if not self.is_production:
            return []
        problems = []
        if not self.TATUM_MAINNET_API_KEY:
            problems.append("TATUM_MAINNET_API_KEY is not set")
        if self.RATE_LIMIT_STORE == "redis" and not self.REDIS_URL:
            problems.append("REDIS_URL is not set (or set RATE_LIMIT_STORE=memory for a single-instance deployment)")
        origins = self.cors_origins
        if not origins:
            problems.append("BACKEND_CORS_ORIGINS is empty")
        for origin in origins:
            if origin == "*" or not origin.startswith("https://") or "localhost" in origin or "127.0.0.1" in origin:
                problems.append(f"BACKEND_CORS_ORIGINS entry is not a public https origin: {origin}")
        hosts = self.allowed_hosts
        if not hosts or "*" in hosts:
            problems.append("ALLOWED_HOSTS must list the API's public host names")
        if bool(self.WALRUS_MEMORY_PRIVATE_KEY) != bool(self.MEMWAL_ACCOUNT_ID):
            problems.append("Walrus Memory is half-configured: set both WALRUS_MEMORY_PRIVATE_KEY and MEMWAL_ACCOUNT_ID, or neither")
        if self.MEMWAL_NAMESPACE_PREFIX == "trace-dev":
            problems.append("MEMWAL_NAMESPACE_PREFIX must not be the development prefix in production")
        return problems

    @property
    def cors_origins(self) -> list[str]:
        # Browsers send origins without a trailing slash; tolerate one in configuration.
        return [origin.strip().rstrip("/") for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip().rstrip("/")]

    @property
    def allowed_hosts(self) -> list[str]:
        return [host.strip() for host in self.ALLOWED_HOSTS.split(",") if host.strip()]


settings = Settings()
