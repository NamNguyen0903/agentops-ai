"""Database coordination record for serialized research admission."""

from sqlalchemy import CheckConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column

from agentops_api.core.orm import Base


class QueueControl(Base):
    __tablename__ = "queue_control"
    __table_args__ = (
        CheckConstraint("id = 1", name="singleton"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
