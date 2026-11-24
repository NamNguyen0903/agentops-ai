
import asyncio

import psycopg

from agentops_api.core.config import Settings


class DatabaseProbe:
    """Bounded PostgreSQL connectivity probe.

    This is not an application connection pool.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = asyncio.Lock()

    async def is_ready(self) -> bool:
        settings = self._settings

        if not settings.database_enabled:
            return False

        if settings.database_password is None:
            return False

        # Reject overlapping probes rather than queueing them.
        if self._lock.locked():
            return False

        async with self._lock:
            try:
                async with asyncio.timeout(3.0):
                    connection = (
                        await psycopg.AsyncConnection.connect(
                            host=settings.database_host,
                            port=settings.database_port,
                            dbname=settings.database_name,
                            user=settings.database_user,
                            password=(
                                settings.database_password
                                .get_secret_value()
                            ),
                            connect_timeout=2,
                            application_name="agentops-readiness",
                            autocommit=True,
                            options=(
                                "-c statement_timeout=1000 "
                                "-c default_transaction_read_only=on"
                            ),
                        )
                    )

                    async with connection:
                        async with connection.cursor() as cursor:
                            await cursor.execute("SELECT 1")
                            result = await cursor.fetchone()

                    return result == (1,)

            except (psycopg.Error, TimeoutError, OSError):
                # Never expose DSNs or driver errors to clients.
                return False
