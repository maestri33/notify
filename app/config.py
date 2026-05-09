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

    # Redis (cache + pub/sub leve)
    redis_url: str = ""

    # RabbitMQ (mensageria entre microservices)
    amqp_url: str = ""

    # SMTP API externa (mail merge)
    smtp_api_base_url: str = "http://mail.local"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""

    # WhatsApp API (Evolution GO / whatsmeow)
    whatsapp_api_base_url: str = "http://whats.local"
    whatsapp_global_api_key: str = ""
    whatsapp_instance_name: str = "default"

    # DeepSeek AI (geracao de titulos, edicao de templates, mensagens)
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_default_model: str = "deepseek-v4-pro"
    deepseek_default_temperature: float = 0.3

    # ElevenLabs TTS (text-to-speech)
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
    elevenlabs_model_id: str = "eleven_v3"
    elevenlabs_output_format: str = "mp3_44100_128"

    # Gemini (geracao de imagens)
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/models"
    gemini_image_model: str = "gemini-3.1-flash-image-preview"
    gemini_vision_model: str = "gemini-3-flash-preview"

    # URL publica deste servico (p/ servir arquivos estaticos via /media)
    # Formato: https://notify.v7m.live
    public_base_url: str = "https://notify.v7m.live"

    # URL interna na DMZ (p/ Evolution baixar midias)
    # Formato: http://notify.local:80
    dmz_base_url: str = "http://notify.local:80"



@lru_cache
def get_settings() -> Settings:
    """Settings singleton — uma instancia por processo."""
    return Settings()
