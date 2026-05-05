"""
Router agregador.

Toda feature nova adiciona seu router aqui via include_router.
"""

from fastapi import APIRouter

from app.api import contacts, health, logs, messages, templates

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(contacts.router, prefix="/contacts", tags=["contacts"])
api_router.include_router(messages.router, prefix="/messages", tags=["messages"])
api_router.include_router(templates.router, prefix="/templates", tags=["templates"])
api_router.include_router(logs.router, prefix="/logs", tags=["logs"])
