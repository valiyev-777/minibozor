from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from the environment (prefix ``MB_``)."""

    model_config = SettingsConfigDict(env_prefix="MB_", env_file=".env", extra="ignore")

    env: str = "dev"
    secret_key: str = "dev-only-secret-change-me-before-shipping-anything"
    database_url: str = "sqlite:///./minibozor.db"

    access_token_minutes: int = 30
    refresh_token_days: int = 60
    algorithm: str = "HS256"

    # Phone login. In dev we never send a real SMS: the code is fixed and echoed
    # back by /auth/otp/request so the apps can be driven end to end offline.
    otp_ttl_seconds: int = 120
    otp_max_attempts: int = 5
    otp_dev_code: str = "123456"

    # Named origins, not a wildcard. The API answers with credentials — the
    # backoffice's refresh cookie rides on them — and a browser refuses
    # ``Access-Control-Allow-Origin: *`` together with credentials outright.
    # Comma-separated; the dev backoffice runs on Vite's default port.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"

    @property
    def cors_origin_list(self) -> list[str]:
        """The configured origins, with any wildcard dropped.

        Dropped rather than honoured: with ``allow_credentials`` on, a browser
        treats a wildcard as no permission at all, so a deployment that sets
        ``*`` would not be permissive — it would be broken, and broken in the
        browser's console rather than in ours.
        """
        named = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return [o for o in named if o != "*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
