from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = (
        "postgresql+psycopg2://notify_svc:YedULhLUuGWLbhO3GSFqW6r@10.10.10.135:6432/main_app"
    )
    db_schema: str = "notify"

    # Redis
    redis_url: str = "redis://:agrKi2YGfuKnlhXT@10.10.10.135:6379/0"

    # Baileys WhatsApp sidecar
    baileys_url: str = "http://localhost:3000"

    # Web Push (VAPID)
    vapid_claim_email: str = "admin@notify.local"
    vapid_private_key: str = ""

    # Runtime
    app_env: str = "development"
    log_level: str = "INFO"


settings = Settings()
