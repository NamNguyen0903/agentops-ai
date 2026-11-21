
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application configuration."""

    model_config = SettingsConfigDict(
        env_prefix="AGENTOPS_",
        extra="ignore",
    )

    app_name: str = Field(
        default="AgentOps AI API",
        min_length=1,
    )

    @field_validator("app_name")
    @classmethod
    def validate_app_name(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("APP_NAME must not be blank")

        return value
