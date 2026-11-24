"""Loopback-only synthetic browser integration server."""

import base64

from agentops_api.core.auth_config import AuthSettings
from agentops_api.core.config import Settings
from agentops_api.main import create_app


class OfflineProvider:
    async def authorize(self):
        raise AssertionError("Live authentication is prohibited")

    async def exchange(self, *args, **kwargs):
        raise AssertionError("Live authentication is prohibited")


settings = Settings(
    database_enabled=True,
    database_host="127.0.0.1",
    database_port=18765,
    database_name="agentops_migration_test",
    database_user="agentops_app",
    database_password="isolated-test-only-runtime",
    auth_review_enabled=True,
    research_queue_capacity=50,
)

auth_settings = AuthSettings(
    client_id="synthetic-browser-client",
    client_secret="synthetic-browser-secret",
    context_key=base64.b64encode(b"x" * 32).decode(),
    origin="http://127.0.0.1:18767",
    development_http=True,
)

app = create_app(
    settings,
    auth_settings=auth_settings,
    auth_provider=OfflineProvider(),
)
