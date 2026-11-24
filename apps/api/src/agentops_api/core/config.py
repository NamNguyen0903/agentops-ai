
from pydantic import (
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application configuration."""

    model_config = SettingsConfigDict(
        env_prefix="AGENTOPS_",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_name: str = Field(
        default="AgentOps AI API",
        min_length=1,
    )

    auth_review_enabled: bool = False

    database_enabled: bool = False
    database_host: str = Field(default="db", min_length=1)
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = Field(default="agentops", min_length=1)
    database_user: str = Field(default="agentops_app", min_length=1)
    database_password: SecretStr | None = None

    @field_validator("app_name")
    @classmethod
    def validate_app_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("APP_NAME must not be blank")
        return value

    @field_validator(
        "database_host",
        "database_name",
        "database_user",
    )
    @classmethod
    def validate_database_field(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError(
                "Database configuration must not be blank"
            )
        return value

    @model_validator(mode="after")
    def validate_database_credentials(self) -> "Settings":
        if self.database_enabled:
            password = self.database_password

            if (
                password is None
                or not password.get_secret_value()
            ):
                raise ValueError(
                    "Database password is required when enabled"
                )

        return self
