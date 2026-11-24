"""Review-only authentication configuration. Disabled by main Settings by default."""
import base64
from urllib.parse import urlsplit

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='AGENTOPS_AUTH_', hide_input_in_errors=True)
    client_id: str
    client_secret: SecretStr
    context_key: SecretStr
    origin: str
    development_http: bool = False

    @model_validator(mode='after')
    def validate_security(self):
        if any(ord(char) <= 32 or ord(char) == 127 for char in self.origin):
            raise ValueError('Origin must not contain whitespace or control characters')
        url = urlsplit(self.origin)
        # urlsplit defers port validation until this property is accessed.
        _ = url.port
        if (url.path or url.query or url.fragment or url.username or url.password
                or not url.hostname or self.origin.endswith('/')):
            raise ValueError('Origin must be an exact origin without path or credentials')
        if self.development_http:
            if url.scheme != 'http' or url.hostname not in ('localhost', '127.0.0.1'):
                raise ValueError('Development HTTP requires loopback origin')
        elif url.scheme != 'https':
            raise ValueError('HTTPS required')
        try:
            key = base64.b64decode(self.context_key.get_secret_value(), validate=True)
        except Exception:
            raise ValueError('Invalid context key encoding') from None
        if len(key) != 32 or not self.client_id or not self.client_secret.get_secret_value():
            raise ValueError('Authentication secrets are required')
        return self

    @property
    def callback_url(self):
        return self.origin + '/api/v1/auth/callback/google'

    @property
    def session_cookie(self):
        return 'agentops_dev_session' if self.development_http else '__Host-agentops_session'

    @property
    def binding_cookie(self):
        return 'agentops_dev_binding' if self.development_http else '__Host-agentops_binding'
