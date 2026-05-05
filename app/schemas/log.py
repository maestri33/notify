from datetime import datetime

from pydantic import BaseModel


class LogCreate(BaseModel):
    message_id: int | None = None
    action: str
    details: dict | None = None


class LogRead(BaseModel):
    id: int
    message_id: int | None = None
    action: str
    details: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
