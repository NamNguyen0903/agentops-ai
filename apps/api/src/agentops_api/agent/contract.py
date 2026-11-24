"""Validated single-agent input and candidate contracts."""

from typing import Any, Literal, TypedDict
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


GRAPH_VERSION = "s04-single-agent-v1"
SCHEMA_VERSION = "s04-state-v1"
FIXTURE_VERSION = "offline-fixture-v1"


class Versions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    graph: Literal["s04-single-agent-v1"] = GRAPH_VERSION
    schema_version: Literal["s04-state-v1"] = SCHEMA_VERSION
    fixture: Literal["offline-fixture-v1"] = FIXTURE_VERSION
    prompt: Literal["none"] = "none"
    model: Literal["none"] = "none"


class BudgetSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_steps: int = Field(default=4, ge=1, le=4)
    model_calls: Literal[0] = 0
    searches: Literal[0] = 0
    retrievals: Literal[0] = 0
    tokens: Literal[0] = 0
    cost_usd: Literal[0] = 0


class GraphInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        hide_input_in_errors=True,
    )

    task_id: UUID
    attempt_id: UUID | None = None
    question: str = Field(min_length=1, max_length=4000)
    scope: dict[str, Any] = Field(default_factory=dict)
    versions: Versions = Field(default_factory=Versions)
    budget: BudgetSnapshot = Field(default_factory=BudgetSnapshot)


class GraphState(TypedDict):
    task_id: str
    attempt_id: str | None
    question: str
    scope: dict[str, Any]
    plan: list[str]
    evidence_ids: list[str]
    coverage: float
    draft_report: None
    result: str | None
    stage: str
    repair_used: bool
    budget_snapshot: dict[str, Any]
    error_category: str | None
    versions: dict[str, Any]


class GraphResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
    )

    task_id: UUID
    attempt_id: UUID | None
    outcome: Literal["insufficient_evidence"]
    stage: Literal["fixture_complete"]
    candidate: str
    evidence_ids: list[str] = Field(default_factory=list)
    coverage: Literal[0.0] = 0.0
    publishable: Literal[False] = False
    error_category: None = None
    versions: Versions
