"""Narrow experiment control for the inspected Authlib 1.9.10 log event.

Install on the emitting logger before requests, not on an ancestor logger.
This is not a general token/header/URL sanitizer or a production configuration.
"""
import logging


class PKCEVerifierFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if (record.name == "authlib.integrations.base_client.sync_app"
                and record.getMessage().startswith("Using code_verifier:")):
            record.msg = "Using code_verifier: [REDACTED]"
            record.args = ()
        return True
