from datetime import datetime

from pydantic import BaseModel


class ContactCreate(BaseModel):
    external_id: str
    phone: str | None = None
    email: str | None = None


class ContactCheckResponse(BaseModel):
    found: bool
    external_id: str | None = None
    phone: str | None = None
    email: str | None = None
    phone_valid: bool | None = None
    email_valid: bool | None = None


class ContactRead(BaseModel):
    id: int
    external_id: str
    phone: str | None = None
    email: str | None = None
    name: str | None = None
    gender: str | None = None
    birth_date: str | None = None
    avatar_url: str | None = None
    profile_data: dict | None = None
    initial_analysis: str | None = None
    is_business: bool = False
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
