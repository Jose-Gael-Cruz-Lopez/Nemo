"""Local settings. Sponsor secrets never enter browser responses or evidence."""
from pathlib import Path

from pydantic import Field, FiniteFloat
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REEFTRACE_", env_file=".env", extra="ignore"
    )
    data_dir: Path = Path("data/local")
    local_token: str = ""
    allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    camera_stale_s: FiniteFloat = Field(default=2.0, ge=0.1, le=10)
    camera_sample_hz: FiniteFloat = Field(default=10.0, ge=1, le=30)
    target_fresh_s: FiniteFloat = Field(default=5.0, ge=1, le=10)
