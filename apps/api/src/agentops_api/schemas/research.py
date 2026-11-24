"""S03 public research contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from agentops_api.repositories.research import ResearchScope


class CreateResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    question: str = Field(min_length=1, max_length=4000)
    scope: ResearchScope = Field(default_factory=ResearchScope)


class ResearchTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    question: str
    scope: ResearchScope
    status: Literal[
        "queued", "running", "completed",
        "insufficient_evidence", "failed", "timed_out",
    ]
    current_stage: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_category: str | None


class ResearchAcceptedResponse(BaseModel):
    task_id: UUID
    status: str
    status_url: str


class ResearchHistoryResponse(BaseModel):
    items: list[ResearchTaskResponse]
    next_cursor: str | None
