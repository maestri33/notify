from collections.abc import Generator

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}
engine = create_engine(settings.database_url, echo=False, connect_args=_connect_args)


if not _is_sqlite:
    from sqlalchemy import event

    @event.listens_for(engine, "begin")
    def _set_search_path(conn):
        conn.exec_driver_sql(f"SET search_path TO {settings.db_schema}, public")


def init_db() -> None:
    if not _is_sqlite:
        with engine.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {settings.db_schema}"))
            conn.commit()
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        if not _is_sqlite:
            session.execute(text(f"SET search_path TO {settings.db_schema}, public"))
        yield session
