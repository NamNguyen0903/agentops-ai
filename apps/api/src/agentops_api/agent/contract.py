"""Validated single-agent input and candidate contracts."""

import json
import math

from typing import Any, Literal, TypedDict
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_validator,
)


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



MAX_SCOPE_BYTES = 8192
MAX_SCOPE_DEPTH = 5


def _validate_json_tree(value: Any, depth: int = 0) -> None:
    """Reject non-JSON values and excessively nested structures."""
    if depth > MAX_SCOPE_DEPTH:
        raise ValueError("scope exceeds maximum nesting depth")

    if value is None or isinstance(value, (str, bool)):
        return

    if isinstance(value, int) and not isinstance(value, bool):
        return

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("scope contains non-finite number")
        return

    if isinstance(value, list):
        for item in value:
            _validate_json_tree(item, depth + 1)
        return

    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("scope keys must be strings")
        for item in value.values():
            _validate_json_tree(item, depth + 1)
        return

    raise ValueError("scope contains unsupported value type")


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

    _scope_snapshot: str = PrivateAttr()

    @staticmethod
    def _canonical_scope(value: dict[str, Any]) -> str:
        return json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )

    def model_post_init(self, __context: Any) -> None:
        """Capture scope after successful model validation."""
        self._scope_snapshot = self._canonical_scope(self.scope)

    def scope_matches_snapshot(self) -> bool:
        """Detect changes to the initially validated scope."""
        return (
            self._canonical_scope(self.scope)
            == self._scope_snapshot
        )

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must contain non-whitespace text")
        return value

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_json_tree(value)

        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")

        if len(encoded) > MAX_SCOPE_BYTES:
            raise ValueError("scope exceeds maximum size")

        return value



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
