"""Allowlisted security diagnostics: never serialize arbitrary log payloads.

Opt-in formatter for reviewed authentication logging configuration. Every handler
and external collector must use this boundary before production auth is enabled.
"""
import json
import logging


SAFE_EVENTS = {'auth.login.failure', 'auth.callback.failure', 'auth.session.failure',
               'auth.csrf.failure', 'auth.logout.failure',
               'research.database.failure',
               'research.request.failure'}
SAFE_ERRORS = {'ValueError', 'TimeoutError', 'InvalidTag', 'OIDCStateUnavailable',
               'OperationalError', 'InvalidClaimError', 'ExpiredTokenError', 'OAuthError'}


def log_failure(event: str, error: Exception) -> None:
    """Emit a fixed diagnostic without raw exception values, URLs or credentials."""
    if event not in SAFE_EVENTS:
        raise ValueError('Unknown security event')
    frames = []
    tb = error.__traceback__
    while tb is not None:
        frames.append({'function': tb.tb_frame.f_code.co_name, 'line': tb.tb_lineno})
        tb = tb.tb_next
    category = type(error).__name__
    logging.getLogger('agentops.auth').warning(event, extra={
        'security_error': category if category in SAFE_ERRORS else 'UnexpectedError',
        'security_frames': frames[-16:],
    })


class PKCELogFilter(logging.Filter):
    """Protect the inspected upstream event before any logger handler sees it."""
    def filter(self, record: logging.LogRecord) -> bool:
        if record.getMessage().startswith('Using code_verifier:'):
            record.msg, record.args = 'Using code_verifier: [REDACTED]', ()
        return True


class SecurityFormatter(logging.Formatter):
    """Discard messages/args/extras/exception values; retain safe diagnostics."""

    def format(self, record: logging.LogRecord) -> str:
        # Values below come from logging machinery; no caller-provided payloads.
        event = 'runtime_event'
        if record.name == 'authlib.integrations.base_client.sync_app':
            event = 'oidc_client_event'
        elif record.name.startswith(('httpx', 'httpcore', 'uvicorn.access')):
            event = 'http_event'
        if record.name == 'agentops.auth' and isinstance(record.msg, str) and record.msg in SAFE_EVENTS:
            event = record.msg
        output = {'event': event, 'level': logging.getLevelName(record.levelno),
                  'line': record.lineno}
        if record.name == 'agentops.auth' and isinstance(record.msg, str) and record.msg in SAFE_EVENTS:
            output['error'] = getattr(record, 'security_error', 'UnexpectedError')
            output['frames'] = getattr(record, 'security_frames', [])
        if record.exc_info:
            # No exception message, locals, source text or arbitrary extra fields.
            output['exception'] = 'exception_raised'
            frames = []
            tb = record.exc_info[2]
            while tb is not None:
                frames.append({'function': tb.tb_frame.f_code.co_name, 'line': tb.tb_lineno})
                tb = tb.tb_next
            output['frames'] = frames
        return json.dumps(output, separators=(',', ':'))


import threading

_logging_lock = threading.RLock()
_active_lifespans = 0
_original_formatters = []
_pkce_filter = None


def acquire_logging_protection() -> None:
    """Activate shared logging protection for a process."""
    global _active_lifespans, _original_formatters, _pkce_filter

    with _logging_lock:
        if _active_lifespans == 0:
            loggers = [
                logging.getLogger(),
                *[
                    value
                    for value in logging.Logger.manager.loggerDict.values()
                    if isinstance(value, logging.Logger)
                ],
            ]

            handlers = {
                handler
                for logger in loggers
                for handler in logger.handlers
            }

            _original_formatters = [
                (handler, handler.formatter)
                for handler in handlers
            ]

            for handler in handlers:
                handler.setFormatter(SecurityFormatter())

            pkce_logger = logging.getLogger(
                "authlib.integrations.base_client.sync_app"
            )

            _pkce_filter = PKCELogFilter()
            pkce_logger.addFilter(_pkce_filter)

        _active_lifespans += 1


def release_logging_protection() -> None:
    """Restore logging only after the last lifespan stops."""
    global _active_lifespans, _original_formatters, _pkce_filter

    with _logging_lock:
        if _active_lifespans == 0:
            return

        _active_lifespans -= 1

        if _active_lifespans != 0:
            return

        pkce_logger = logging.getLogger(
            "authlib.integrations.base_client.sync_app"
        )

        if _pkce_filter is not None:
            pkce_logger.removeFilter(_pkce_filter)

        for handler, formatter in _original_formatters:
            handler.setFormatter(formatter)

        _original_formatters = []
        _pkce_filter = None
