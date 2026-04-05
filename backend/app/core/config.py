from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/robo"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Bybit
    bybit_api_key: str = ""
    bybit_api_secret: str = ""
    bybit_testnet: bool = True

    # App
    env: str = "development"
    log_level: str = "INFO"

    @property
    def is_development(self) -> bool:
        return self.env == "development"


settings = Settings()
