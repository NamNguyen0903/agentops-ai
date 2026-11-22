
"""Alembic environment for AgentOps AI.

AG-003.3A: infrastructure only.
No approved application models or migration revisions exist yet.
"""

from alembic import context
from alembic.util import CommandError

from agentops_api.core.orm import APP_SCHEMA, Base


def run_migrations_online() -> None:
    """Prevent online migrations before schema approval."""

    if not Base.metadata.tables:
        raise CommandError(
            "AG-003.3A: Online migrations are disabled "
            "until application models and schema are approved."
        )

    raise CommandError(
        "AG-003.3A: Migration execution is not enabled. "
        "Approve the schema and dedicated migration role first."
    )


def run_migrations_offline() -> None:
    """Prevent offline migration SQL generation."""

    raise CommandError(
        "AG-003.3A: Offline migration execution "
        "is disabled."
    )


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
