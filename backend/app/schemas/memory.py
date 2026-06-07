from datetime import datetime
from pydantic import BaseModel


class ProfileEntry(BaseModel):
    key: str
    value: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProfileRead(BaseModel):
    entries: list[ProfileEntry]


class ProfileUpsert(BaseModel):
    key: str
    value: str


class ProfileEntryUpdate(BaseModel):
    value: str