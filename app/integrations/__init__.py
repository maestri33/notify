"""
Integracoes com servicos externos.

Cada arquivo aqui encapsula a comunicacao com um servico externo especifico.
"""

from app.integrations.deepseek import DeepSeekClient
from app.integrations.elevenlabs import ElevenLabsClient
from app.integrations.gemini import GeminiClient
from app.integrations.smtp import SMTPClient
from app.integrations.whatsapp import WhatsAppClient

__all__ = [
    "DeepSeekClient",
    "ElevenLabsClient",
    "GeminiClient",
    "SMTPClient",
    "WhatsAppClient",
]
