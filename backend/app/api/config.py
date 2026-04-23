"""API endpoints for ServiceConfig (GET + PUT)."""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.schemas import ConfigOut, ConfigUpdate
from app.db import get_session
from app.models.service_config import ServiceConfig
from app.models._common import utcnow

router = APIRouter(prefix="/config", tags=["config"])


@router.get("", response_model=ConfigOut)
def get_config(session: Session = Depends(get_session)) -> ServiceConfig:
    cfg = session.get(ServiceConfig, 1)
    return cfg


@router.put("", response_model=ConfigOut)
def update_config(
    payload: ConfigUpdate,
    session: Session = Depends(get_session),
) -> ServiceConfig:
    cfg = session.get(ServiceConfig, 1)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cfg, field, value)
    cfg.updated_at = utcnow()
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return cfg
