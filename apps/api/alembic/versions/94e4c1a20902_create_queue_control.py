"""Create the singleton research admission coordination record."""

from alembic import op
import sqlalchemy as sa

revision = "94e4c1a20902"
down_revision = "83d3b0f10901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "queue_control",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=False),
        sa.CheckConstraint(
            "id = 1",
            name=op.f("ck_queue_control_singleton"),
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_queue_control"),
        ),
        schema="app",
    )
    op.execute("INSERT INTO app.queue_control (id) VALUES (1)")
    op.execute(
        "REVOKE ALL ON TABLE app.queue_control FROM PUBLIC"
    )
    op.execute(
        "REVOKE ALL ON TABLE app.queue_control FROM agentops_app"
    )
    op.execute(
        "GRANT SELECT, UPDATE ON TABLE app.queue_control TO agentops_app"
    )


def downgrade() -> None:
    op.drop_table("queue_control", schema="app")
