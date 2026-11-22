"""Non-secret configuration for synthetic OIDC tests."""
from dataclasses import dataclass


@dataclass(frozen=True)
class OIDCConfig:
    issuer: str = "https://fake-idp.example.test"
    client_id: str = "agentops-poc-client"
    redirect_uri: str = "http://localhost:8000/api/v1/auth/callback/google"
    state_ttl_seconds: int = 300
    session_idle_seconds: int = 1800
    session_absolute_seconds: int = 43200

    def __post_init__(self) -> None:
        if not self.issuer.startswith("https://"):
            raise ValueError("OIDC issuer must be HTTPS")
        if min(self.state_ttl_seconds, self.session_idle_seconds, self.session_absolute_seconds) <= 0:
            raise ValueError("Deadlines must be positive")
