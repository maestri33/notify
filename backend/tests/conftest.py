import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app import models  # noqa: F401 -- register metadata
from app.db import get_session
from app.main import app
from app.models import EmailTemplate, ServiceConfig
from app.models.email_template import DEFAULT_HTML, DEFAULT_SUBJECT
from app.services.baileys import BaileysError, get_baileys


class FakeBaileys:
    """Simulates the sidecar being offline — recipient CRUD must keep working."""

    def validate(self, phone):
        raise BaileysError("offline")


class FakeQueue:
    """In-memory queue replacement — records enqueued calls, never runs them."""

    enqueued: list[tuple] = []

    def enqueue(self, func, *args, **kwargs):
        self.enqueued.append((func, args, kwargs))

        class _Job:
            id = "fake-job"

        return _Job()


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(EmailTemplate(id=1, subject=DEFAULT_SUBJECT, html_body=DEFAULT_HTML))
        s.add(ServiceConfig(id=1))
        s.commit()
        yield s


@pytest.fixture
def client(session, monkeypatch):
    def override():
        yield session

    app.dependency_overrides[get_session] = override
    app.dependency_overrides[get_baileys] = lambda: FakeBaileys()

    fake_queue = FakeQueue()
    FakeQueue.enqueued = []
    monkeypatch.setattr("app.api.notifications.get_queue", lambda _ch: fake_queue)

    with TestClient(app) as c:
        c.enqueued = FakeQueue.enqueued  # expose for assertions
        yield c
    app.dependency_overrides.clear()
