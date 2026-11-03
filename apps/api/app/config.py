from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/hems.db"
    artifact_root: Path = Path("./data/artifacts")
    openstudio_cli: str = ""
    openstudio_hpxml_dir: Path | None = None
    openstudio_hpxml_version: str = "1.12.0"
    worker_inline: bool = False
    worker_poll_seconds: float = 1.0
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    smarty_auth_id: str = ""
    smarty_auth_token: str = ""
    google_places_api_key: str = ""
    google_maps_api_key: str = ""
    mapbox_access_token: str = ""
    arcgis_geocode_token: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]


settings = Settings()
