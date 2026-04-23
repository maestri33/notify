from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/notify.db"
    redis_url: str = "redis://localhost:6379/0"
    baileys_url: str = "http://localhost:3000"
    app_env: str = "development"
    log_level: str = "INFO"


settings = Settings()
