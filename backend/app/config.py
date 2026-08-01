from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://tournament:tournament@localhost:5433/tournament_tracker"
    osirion_base_url: str = "https://fnapi.osirion.gg"
    osirion_api_key: str = ""
    scheduler_enabled: bool = True


settings = Settings()
