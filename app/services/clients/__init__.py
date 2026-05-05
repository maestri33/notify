"""
Clientes para APIs externas.

Cada arquivo aqui encapsula a comunicacao com um servico externo especifico.
"""

from app.services.clients.deepseek import DeepSeekClient
from app.services.clients.elevenlabs import ElevenLabsClient
from app.services.clients.gemini import GeminiClient
from app.services.clients.smtp import SMTPClient
from app.services.clients.whatsapp import WhatsAppClient

__all__ = ["DeepSeekClient", "ElevenLabsClient", "GeminiClient", "SMTPClient", "WhatsAppClient"]
