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

    # What a courier earns for one delivery, in so'm.
    #
    # A flat rate rather than a share of the order: a courier carrying a
    # 4 000 000 so'm television up three flights is doing the same work as one
    # carrying a t-shirt, and paying by the basket would make the cheap stops
    # nobody's first choice — which is exactly the wrong incentive in a shop
    # where couriers pick their own work.
    #
    # Here rather than in a table because it is one number today. The day it
    # differs by distance or by hour it wants a tariff of its own, and this is
    # the line that moves into it.
    courier_fee_per_delivery: int = 15_000

    # Named origins, not a wildcard. The API answers with credentials — the
    # backoffice's refresh cookie rides on them — and a browser refuses
    # ``Access-Control-Allow-Origin: *`` together with credentials outright.
    #
    # One staff application now, on 5173, where there were three. It is named
    # on both hostnames because ``localhost`` and ``127.0.0.1`` are different
    # origins to a browser and people type both.
    #
    # Comma-separated, and a deployment overrides the lot with MB_CORS_ORIGINS:
    # these are development ports and belong nowhere else.
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
