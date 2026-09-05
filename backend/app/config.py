from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    backend_port: int
    database_url: str
    cors_origins: str

    llm_model: str
    api_key: str
    base_url: str

    openpencil_mcp_auth_token: str = ""
    mcp_timeout_seconds: int
    design_data_dir: Path = PROJECT_DIR.parent / "designer-data"
    openpencil_cli: str = "openpencil"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def sqlite_path(self) -> Path:
        prefix = "sqlite:///"
        raw = self.database_url.removeprefix(prefix)
        path = Path(raw)
        if not path.is_absolute():
            path = PROJECT_DIR / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
