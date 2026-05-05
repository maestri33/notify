"""
Configuracao do servico — leitura do .env via pydantic-settings.

Tudo que vier de fora (URL de banco, broker, redis, secrets) passa por aqui.
Nao leia env var direto fora deste modulo.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Identificacao do servico
    service_name: str = "notify"
    env: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"
    port: int = 80

    # Banco — cada servico tem o seu proprio
    database_url: str = "sqlite://data/app.db"

    # SMTP API externa (mail merge)
    smtp_api_base_url: str = "http://10.10.10.150"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""

    # WhatsApp API (Evolution GO / whatsmeow)
    whatsapp_api_base_url: str = "http://10.10.10.149"
    whatsapp_global_api_key: str = ""
    whatsapp_instance_name: str = "default"

    # DeepSeek AI (geracao de titulos, edicao de templates)
    deepseek_api_key: str = ""

    # ElevenLabs TTS (text-to-speech)
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"

    # Gemini (geracao de imagens)
    gemini_api_key: str = ""

    # URL publica deste servico (p/ servir arquivos estaticos via /files)
    public_base_url: str = "http://10.10.10.144:80"


@lru_cache
def get_settings() -> Settings:
    """Settings singleton — uma instancia por processo."""
    return Settings()
