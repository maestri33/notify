"""Read ServiceConfig / EmailTemplate from DB (used by workers)."""

from sqlmodel import Session

from app.db import engine
from app.models import EmailTemplate, ServiceConfig


def load_service_config() -> ServiceConfig:
    with Session(engine) as s:
        cfg = s.get(ServiceConfig, 1)
        if not cfg:
            raise RuntimeError("ServiceConfig row missing — run migrations")
        return cfg


def load_email_template() -> EmailTemplate:
    with Session(engine) as s:
        tpl = s.get(EmailTemplate, 1)
        if not tpl:
            raise RuntimeError("EmailTemplate row missing — run migrations")
        return tpl
