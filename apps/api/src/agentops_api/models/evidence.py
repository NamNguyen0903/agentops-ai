"""S06 immutable research evidence persistence model.

DDL is managed by the S06 additive Alembic migration.
Only disposable migration testing is authorized.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from agentops_api.core.orm import Base
from agentops_api.models import research as _research


class ResearchEvidence(Base):
    __tablename__ = "research_evidence"

    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id", "task_id"],
            ["app.research_tasks.owner_id", "app.research_tasks.id"],
            name="fk_research_evidence_owner_task",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "owner_id",
            "task_id",
            "execution_id",
            "id",
            name="uq_research_evidence_scope_id",
        ),
        CheckConstraint(
            "length(btrim(title)) BETWEEN 1 AND 512",
            name="title_nonempty",
        ),
        CheckConstraint(
            "length(excerpt) BETWEEN 1 AND 4096 "
            "AND length(btrim(excerpt)) > 0",
            name="excerpt_bounds",
        ),
        CheckConstraint(
            "source_url ~ '^https?://' "
            "AND retrieved_url ~ '^https?://'",
            name="url_schemes",
        ),
        CheckConstraint(
            "octet_length(content_hash) = 32",
            name="hash_length",
        ),
        CheckConstraint(
            "acquisition_method = 'fixture_retrieval'",
            name="acquisition_method",
        ),
        CheckConstraint(
            "synthetic IS TRUE",
            name="synthetic_only",
        ),
        CheckConstraint(
            "published_at IS NULL",
            name="publication_unknown",
        ),
        Index(
            "ix_research_evidence_scope",
            "owner_id",
            "task_id",
            "execution_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)

    owner_id: Mapped[UUID] = mapped_column(nullable=False)
    task_id: Mapped[UUID] = mapped_column(nullable=False)
    execution_id: Mapped[UUID] = mapped_column(nullable=False)

    title: Mapped[str] = mapped_column(
        String(512), nullable=False
    )

    source_url: Mapped[str] = mapped_column(
        String(2048), nullable=False
    )

    retrieved_url: Mapped[str] = mapped_column(
        String(2048), nullable=False
    )

    excerpt: Mapped[str] = mapped_column(
        Text(), nullable=False
    )

    acquisition_method: Mapped[str] = mapped_column(
        String(32), nullable=False
    )

    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    content_hash: Mapped[bytes] = mapped_column(
        LargeBinary(32), nullable=False
    )

    synthetic: Mapped[bool] = mapped_column(
        Boolean(), nullable=False
    )
