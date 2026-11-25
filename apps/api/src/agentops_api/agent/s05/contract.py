"""Strict, versioned contracts for the offline S05 workflow.

Execution limits are application-owned. These contracts do not
execute providers, perform I/O or authorize task publication.
"""

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
    model_validator,
)


GRAPH_VERSION = "s05-specialized-agent-v1"
SCHEMA_VERSION = "s05-state-v1"
FIXTURE_VERSION = "s05-offline-fixture-v1"

MAX_QUESTION_LENGTH = 4000
MAX_SCOPE_BYTES = 8192
MAX_SCOPE_DEPTH = 5

MAX_SUBQUESTIONS = 4
MAX_ADAPTER_INVOCATIONS = 4
MAX_REPAIR_ATTEMPTS = 1
INITIAL_RECURSION_LIMIT = 12
MAX_RUNTIME_SECONDS = 30


class StrictContract(BaseModel):
    """Shared configuration for S05 typed contracts."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        hide_input_in_errors=True,
        validate_default=True,
        revalidate_instances="always",
    )


class S05Versions(StrictContract):
    """Fixed version metadata for the offline S05 baseline."""

    graph: Literal["s05-specialized-agent-v1"] = GRAPH_VERSION
    schema_version: Literal["s05-state-v1"] = SCHEMA_VERSION
    fixture: Literal["s05-offline-fixture-v1"] = FIXTURE_VERSION
    model: Literal["none"] = "none"
    prompt: Literal["none"] = "none"


class ExecutionPolicy(StrictContract):
    """Application-owned limits, not caller-controlled settings."""

    max_subquestions: Literal[4] = MAX_SUBQUESTIONS
    max_adapter_invocations: Literal[4] = MAX_ADAPTER_INVOCATIONS
    max_repair_attempts: Literal[1] = MAX_REPAIR_ATTEMPTS
    recursion_limit: Literal[12] = INITIAL_RECURSION_LIMIT
    soft_deadline_seconds: Literal[30] = MAX_RUNTIME_SECONDS

    live_model_calls: Literal[0] = 0
    live_search_calls: Literal[0] = 0
    live_retrieval_calls: Literal[0] = 0
    live_tokens: Literal[0] = 0
    paid_cost_usd: Literal[0] = 0
    durable_checkpoints: Literal[0] = 0

    publishable: Literal[False] = False

    @field_validator("*", mode="before")
    @classmethod
    def validate_exact_policy_types(
        cls,
        value: Any,
        info: Any,
    ) -> Any:
        expected_type = (
            bool if info.field_name == "publishable" else int
        )

        if type(value) is not expected_type:
            raise ValueError("invalid execution policy value type")

        return value


class ExecutionCounters(StrictContract):
    """Bounded accounting values, separate from policy limits."""

    adapter_invocations: int = Field(
        default=0,
        ge=0,
        le=MAX_ADAPTER_INVOCATIONS,
    )

    repair_attempts: int = Field(
        default=0,
        ge=0,
        le=MAX_REPAIR_ATTEMPTS,
    )

    live_model_calls: Literal[0] = 0
    live_search_calls: Literal[0] = 0
    live_retrieval_calls: Literal[0] = 0
    live_tokens: Literal[0] = 0
    paid_cost_usd: Literal[0] = 0

    @field_validator("*", mode="before")
    @classmethod
    def validate_exact_counter_types(cls, value: Any) -> Any:
        if type(value) is not int:
            raise ValueError("invalid execution counter type")

        return value

    @model_validator(mode="after")
    def validate_counter_consistency(self) -> "ExecutionCounters":
        if self.repair_attempts > self.adapter_invocations:
            raise ValueError(
                "repair attempts cannot exceed adapter invocations"
            )

        return self


def _validate_json_tree(value: Any, depth: int = 0) -> None:
    """Validate exact JSON-compatible types and nesting limits."""

    if depth > MAX_SCOPE_DEPTH:
        raise ValueError("scope exceeds maximum nesting depth")

    value_type = type(value)

    if value is None or value_type in (str, bool, int):
        return

    if value_type is float:
        if not math.isfinite(value):
            raise ValueError("scope contains non-finite number")
        return

    if value_type is list:
        for item in value:
            _validate_json_tree(item, depth + 1)
        return

    if value_type is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("scope keys must be strings")

            _validate_json_tree(item, depth + 1)
        return

    raise ValueError("scope contains unsupported value type")


def _canonical_scope_json(value: dict[str, Any]) -> str:
    """Validate and serialize scope without retaining mutable aliases."""

    if type(value) is not dict:
        raise ValueError("scope must be a JSON object")

    _validate_json_tree(value)

    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )

        size = len(encoded.encode("utf-8"))

    except (ValueError, UnicodeError, OverflowError):
        raise ValueError("scope cannot be encoded safely") from None

    if size > MAX_SCOPE_BYTES:
        raise ValueError("scope exceeds maximum size")

    return encoded


class S05GraphInput(StrictContract):
    """Untrusted research input, without policy or version authority."""

    task_id: UUID
    attempt_id: UUID | None = None

    question: str = Field(
        min_length=1,
        max_length=MAX_QUESTION_LENGTH,
    )

    scope: dict[str, Any] = Field(default_factory=dict)

    _input_snapshot: tuple[
        UUID, UUID | None, str, str
    ] | None = PrivateAttr(default=None)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "question must contain non-whitespace text"
            )

        try:
            value.encode("utf-8")
        except UnicodeError:
            raise ValueError(
                "question cannot be encoded safely"
            ) from None

        return value

    @field_validator("scope", mode="before")
    @classmethod
    def validate_scope(cls, value: Any) -> dict[str, Any]:
        return json.loads(_canonical_scope_json(value))


    def _current_input_snapshot(
        self,
    ) -> tuple[UUID, UUID | None, str, str]:
        """Return an exact-type, canonical snapshot of input fields."""

        if type(self.task_id) is not UUID:
            raise ValueError("invalid task identity")

        if (
            self.attempt_id is not None
            and type(self.attempt_id) is not UUID
        ):
            raise ValueError("invalid attempt identity")

        if type(self.question) is not str:
            raise ValueError("invalid question type")

        if not 1 <= len(self.question) <= MAX_QUESTION_LENGTH:
            raise ValueError("invalid question length")

        self.validate_question(self.question)

        return (
            self.task_id,
            self.attempt_id,
            self.question,
            _canonical_scope_json(self.scope),
        )

    @model_validator(mode="after")
    def capture_input_snapshot(self) -> "S05GraphInput":
        """Capture a snapshot only for normally validated input."""

        self._input_snapshot = self._current_input_snapshot()
        return self

    def verified_input_snapshot(
        self,
    ) -> tuple[UUID, UUID | None, str, str]:
        """Reject missing snapshots and changed input fields."""

        try:
            original = self._input_snapshot

            if type(original) is not tuple or len(original) != 4:
                raise ValueError("missing input snapshot")

            if type(original[0]) is not UUID:
                raise ValueError("invalid snapshot task identity")

            if (
                original[1] is not None
                and type(original[1]) is not UUID
            ):
                raise ValueError("invalid snapshot attempt identity")

            if type(original[2]) is not str:
                raise ValueError("invalid snapshot question")

            if type(original[3]) is not str:
                raise ValueError("invalid snapshot scope")

            current = self._current_input_snapshot()

            if original != current:
                raise ValueError("input changed after validation")

        except (ValueError, TypeError, AttributeError, OverflowError):
            raise ValueError("invalid input integrity") from None

        return original


# Structured offline plan, fixture and outcome contracts.


MAX_SUBQUESTION_LENGTH = 1000
MAX_QUERY_LENGTH = 1000
MAX_ASSUMPTIONS = 4
MAX_FIXTURE_RECORDS = 20
MAX_FIXTURE_TEXT_LENGTH = 4000
MAX_REPORT_SECTIONS = 8
MAX_REPORT_TEXT_LENGTH = 4000
MAX_RESEARCH_NOTES = 8


def _validate_nonblank_text(value: str) -> str:
    if not value.strip():
        raise ValueError("text must not be blank")

    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ValueError("text cannot be encoded safely") from None

    return value


def _validate_note_collection(
    values: tuple[str, ...],
) -> tuple[str, ...]:
    for value in values:
        if len(value) > MAX_SUBQUESTION_LENGTH:
            raise ValueError("note exceeds maximum length")

        _validate_nonblank_text(value)

    return values


def _validate_fixture_coverage(value: Any) -> float:
    if type(value) is not float:
        raise ValueError("invalid fixture coverage type")

    if not math.isfinite(value):
        raise ValueError("fixture coverage must be finite")

    if not 0.0 <= value <= 1.0:
        raise ValueError("fixture coverage outside valid range")

    return value


class ResearchSubquestion(StrictContract):
    """One structured question and its corresponding fixture query."""

    subquestion_id: str = Field(
        pattern=r"^q[1-4]$",
    )

    question: str = Field(
        min_length=1,
        max_length=MAX_SUBQUESTION_LENGTH,
    )

    query: str = Field(
        min_length=1,
        max_length=MAX_QUERY_LENGTH,
    )

    @field_validator("question", "query")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _validate_nonblank_text(value)


class ResearchPlan(StrictContract):
    """Bounded plan with no tool or permission authority."""

    subquestions: tuple[ResearchSubquestion, ...] = Field(
        min_length=1,
        max_length=MAX_SUBQUESTIONS,
    )

    assumptions: tuple[str, ...] = Field(
        default=(),
        max_length=MAX_ASSUMPTIONS,
    )

    @field_validator("assumptions")
    @classmethod
    def validate_assumptions(
        cls,
        values: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _validate_note_collection(values)

    @model_validator(mode="after")
    def validate_unique_questions(self) -> "ResearchPlan":
        ids = [
            item.subquestion_id
            for item in self.subquestions
        ]

        if len(ids) != len(set(ids)):
            raise ValueError("duplicate subquestion identity")

        return self


class FixtureReference(StrictContract):
    """Synthetic fixture identity, not an externally stored evidence ID."""

    fixture_id: str = Field(
        min_length=1,
        max_length=80,
        pattern=r"^fixture-[a-z0-9-]+$",
    )

    task_id: UUID
    attempt_id: UUID | None = None

    fixture_version: Literal[
        "s05-offline-fixture-v1"
    ] = FIXTURE_VERSION

    source: Literal[
        "application-owned-synthetic-fixture"
    ] = "application-owned-synthetic-fixture"


class FixtureRecord(StrictContract):
    """Application-owned synthetic content with explicit provenance."""

    reference: FixtureReference

    subquestion_id: str = Field(
        pattern=r"^q[1-4]$",
    )

    title: str = Field(
        min_length=1,
        max_length=200,
    )

    content: str = Field(
        min_length=1,
        max_length=MAX_FIXTURE_TEXT_LENGTH,
    )

    synthetic: Literal[True] = True

    @field_validator("title", "content")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _validate_nonblank_text(value)

    @field_validator("synthetic", mode="before")
    @classmethod
    def validate_synthetic(cls, value: Any) -> bool:
        if value is not True:
            raise ValueError("fixture must remain synthetic")

        return value


class ResearchOutput(StrictContract):
    """Bounded fixture-only research output."""

    records: tuple[FixtureRecord, ...] = Field(
        default=(),
        max_length=MAX_FIXTURE_RECORDS,
    )

    gaps: tuple[str, ...] = Field(
        default=(),
        max_length=MAX_RESEARCH_NOTES,
    )

    conflicts: tuple[str, ...] = Field(
        default=(),
        max_length=MAX_RESEARCH_NOTES,
    )

    fixture_coverage: float = 0.0

    @field_validator("gaps", "conflicts")
    @classmethod
    def validate_notes(
        cls,
        values: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _validate_note_collection(values)

    @field_validator("fixture_coverage", mode="before")
    @classmethod
    def validate_coverage(cls, value: Any) -> float:
        return _validate_fixture_coverage(value)

    @model_validator(mode="after")
    def validate_records(self) -> "ResearchOutput":
        ids = [
            record.reference.fixture_id
            for record in self.records
        ]

        if len(ids) != len(set(ids)):
            raise ValueError("duplicate fixture identity")

        if not self.records and self.fixture_coverage != 0.0:
            raise ValueError(
                "empty fixture output must have zero coverage"
            )

        return self


class ReportSection(StrictContract):
    """Structured synthetic report section."""

    heading: str = Field(
        min_length=1,
        max_length=200,
    )

    content: str = Field(
        min_length=1,
        max_length=MAX_REPORT_TEXT_LENGTH,
    )

    fixture_references: tuple[FixtureReference, ...] = Field(
        min_length=1,
        max_length=MAX_FIXTURE_RECORDS,
    )

    @field_validator("heading", "content")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _validate_nonblank_text(value)

    @model_validator(mode="after")
    def validate_references(self) -> "ReportSection":
        ids = [
            reference.fixture_id
            for reference in self.fixture_references
        ]

        if len(ids) != len(set(ids)):
            raise ValueError("duplicate section fixture reference")

        return self


class DraftReport(StrictContract):
    """Synthetic offline candidate, never a published research report."""

    title: str = Field(
        min_length=1,
        max_length=200,
    )

    summary: str = Field(
        min_length=1,
        max_length=MAX_REPORT_TEXT_LENGTH,
    )

    sections: tuple[ReportSection, ...] = Field(
        min_length=1,
        max_length=MAX_REPORT_SECTIONS,
    )

    limitations: tuple[str, ...] = Field(
        min_length=1,
        max_length=MAX_RESEARCH_NOTES,
    )

    synthetic: Literal[True] = True

    @field_validator("title", "summary")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _validate_nonblank_text(value)

    @field_validator("limitations")
    @classmethod
    def validate_limitations(
        cls,
        values: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _validate_note_collection(values)

    @field_validator("synthetic", mode="before")
    @classmethod
    def validate_synthetic(cls, value: Any) -> bool:
        if value is not True:
            raise ValueError("report must remain synthetic")

        return value


GraphStage = Literal[
    "pending",
    "planned",
    "researched",
    "evidence_validated",
    "written",
    "report_validated",
    "candidate_ready",
    "insufficient_evidence",
    "failed",
]

ErrorCategory = Literal[
    "invalid_input",
    "invalid_output",
    "execution_failed",
    "deadline_exceeded",
    "budget_exceeded",
    "security_violation",
]


class S05GraphResult(StrictContract):
    """Validated non-publishable outcome proposal."""

    task_id: UUID
    attempt_id: UUID | None = None

    outcome: Literal[
        "candidate_ready",
        "insufficient_evidence",
    ]

    stage: Literal[
        "candidate_ready",
        "insufficient_evidence",
    ]

    candidate: DraftReport | None = None

    evidence_ids: tuple[str, ...] = Field(
        default=(),
        max_length=0,
    )

    coverage: Literal[0.0] = 0.0

    fixture_coverage: float = 0.0

    publishable: Literal[False] = False

    error_category: None = None

    versions: S05Versions = Field(
        default_factory=S05Versions,
    )

    counters: ExecutionCounters = Field(
        default_factory=ExecutionCounters,
    )

    @field_validator("coverage", mode="before")
    @classmethod
    def validate_real_coverage(cls, value: Any) -> float:
        if type(value) is not float or value != 0.0:
            raise ValueError("real evidence coverage must be zero")

        return value

    @field_validator("fixture_coverage", mode="before")
    @classmethod
    def validate_coverage(cls, value: Any) -> float:
        return _validate_fixture_coverage(value)

    @field_validator("publishable", mode="before")
    @classmethod
    def validate_publication(cls, value: Any) -> bool:
        if value is not False:
            raise ValueError("publication is not authorized")

        return value

    @model_validator(mode="after")
    def validate_outcome(self) -> "S05GraphResult":
        if self.stage != self.outcome:
            raise ValueError("outcome and stage must agree")

        if self.outcome == "insufficient_evidence":
            if self.candidate is not None:
                raise ValueError(
                    "abstention cannot contain a report candidate"
                )

            return self

        if self.candidate is None:
            raise ValueError("candidate report is required")

        if self.fixture_coverage <= 0.0:
            raise ValueError(
                "candidate requires positive fixture coverage"
            )

        for section in self.candidate.sections:
            for reference in section.fixture_references:
                if reference.task_id != self.task_id:
                    raise ValueError("cross-task fixture reference")

                if reference.attempt_id != self.attempt_id:
                    raise ValueError("cross-attempt fixture reference")

        return self


class S05GraphState(TypedDict):
    """Ephemeral graph state; TypedDict is not runtime validation."""

    task_id: str
    attempt_id: str | None
    question: str
    scope: dict[str, Any]

    plan: ResearchPlan | None
    research_output: ResearchOutput | None

    evidence_ids: tuple[str, ...]
    coverage: float
    fixture_coverage: float

    draft_report: DraftReport | None
    result: S05GraphResult | None

    stage: GraphStage
    repair_used: bool

    budget_snapshot: ExecutionPolicy
    counters: ExecutionCounters
    error_category: ErrorCategory | None
    versions: S05Versions
