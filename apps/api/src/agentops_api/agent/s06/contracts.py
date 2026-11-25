"""Strict S06 acquisition contracts."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .errors import AcquisitionError, ErrorCode


class StrictContract(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
    )


class AcquisitionContext(StrictContract):
    task_id: UUID
    execution_id: UUID


class SearchRequest(StrictContract):
    query: str = Field(min_length=1, max_length=1024)
    max_results: int = Field(default=10, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def check_query(cls, value: str) -> str:
        if not value.strip() or any(
            ord(c) < 32 or ord(c) == 127 for c in value
        ):
            raise ValueError("invalid query")
        return value.strip()


class SearchHit(StrictContract):
    title: str = Field(min_length=1, max_length=512)
    url: str = Field(min_length=1, max_length=2048)
    snippet: str = Field(max_length=4096)

    @field_validator("title")
    @classmethod
    def check_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("invalid title")
        return value.strip()


class SearchResult(StrictContract):
    hits: tuple[SearchHit, ...] = Field(max_length=10)
    synthetic: bool = True

    @field_validator("synthetic")
    @classmethod
    def check_synthetic(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("offline result required")
        return value


class RetrievalRequest(StrictContract):
    url: str = Field(min_length=1, max_length=2048)


class RetrievedPage(StrictContract):
    source_url: str = Field(min_length=1, max_length=2048)
    retrieved_url: str = Field(min_length=1, max_length=2048)
    content_type: str = Field(min_length=1, max_length=128)
    body: bytes = Field(max_length=1048576)
    synthetic: bool

    @field_validator("synthetic")
    @classmethod
    def check_synthetic(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("offline page required")
        return value


def _plain_payload(value):
    """Reconstruct trusted validation input without coercive dumping."""
    if isinstance(value, BaseModel):
        if type(value) not in {
            AcquisitionContext,
            SearchRequest,
            SearchHit,
            SearchResult,
            RetrievalRequest,
            RetrievedPage,
        }:
            raise ValueError("unknown contract type")

        fields = type(value).model_fields

        if set(vars(value)) != set(fields):
            raise ValueError("unexpected contract fields")

        if value.__pydantic_extra__:
            raise ValueError("unexpected extra fields")

        return {
            key: _plain_payload(item)
            for key, item in vars(value).items()
        }

    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise ValueError("invalid field key")
        return {
            key: _plain_payload(item)
            for key, item in value.items()
        }

    if type(value) is tuple:
        return tuple(_plain_payload(item) for item in value)

    if type(value) in {str, int, bool, bytes, UUID}:
        return value

    if value is None:
        return None

    raise ValueError("unsupported contract value")


def validate_contract(model, value, *, output=False):
    try:
        if type(value) not in {model, dict}:
            raise ValueError("invalid payload")

        value = _plain_payload(value)

        if type(value) is not dict:
            raise ValueError("invalid payload")

        return model.model_validate(value, strict=True)
    except Exception:
        code = (
            ErrorCode.INVALID_RESPONSE
            if output else ErrorCode.INVALID_INPUT
        )
        raise AcquisitionError(code) from None
