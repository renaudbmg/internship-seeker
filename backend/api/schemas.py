from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    company: str
    source: str
    url: str
    location: str
    description: str
    summary_ai: str | None
    score_ai: int | None
    status: str
    notes: str | None
    scraped_at: datetime
    seen: bool


class JobListOut(BaseModel):
    total: int
    items: list[JobOut]


class StatusUpdate(BaseModel):
    status: str  # to_review | interested | applied | rejected


class NotesUpdate(BaseModel):
    notes: str


class StatsOut(BaseModel):
    total: int
    by_source: dict[str, int]
    by_status: dict[str, int]
    by_day: dict[str, int]
