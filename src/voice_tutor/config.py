from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", extra="ignore", hide_input_in_errors=True
    )
    app_mode: Literal["fake", "live"] = "fake"
    app_origin: str = "http://localhost:8000"
    elevenlabs_api_key: SecretStr = SecretStr("")
    elevenlabs_agent_id: str = ""
    openai_api_key: SecretStr = SecretStr("")
    openai_review_model: str = ""
    transcript_wait_seconds: float = Field(default=90, gt=0, le=180)
    review_timeout_seconds: float = Field(default=60, gt=0, le=120)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @model_validator(mode="after")
    def live_config(self) -> "Settings":
        if self.app_origin not in ("http://localhost:8000", "http://127.0.0.1:8000"):
            raise ValueError("APP_ORIGIN must be a local port-8000 origin")
        if self.app_mode == "live":
            fields = (
                "elevenlabs_api_key",
                "elevenlabs_agent_id",
                "openai_api_key",
                "openai_review_model",
            )
            missing = [
                name.upper()
                for name in fields
                if not (
                    getattr(self, name).get_secret_value()
                    if isinstance(getattr(self, name), SecretStr)
                    else getattr(self, name)
                )
            ]
            if missing:
                raise ValueError("Live mode requires: " + ", ".join(missing))
        return self
