from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./holistic.db"
    SECRET_KEY: str = "dev-insecure-secret-change-me-0123456789abcdef"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    DEFAULT_LOCALE: str = "fr"
    ALLOWED_LOCALES: tuple[str, ...] = ("fr", "en")
    DEFAULT_SIGNAL_ALERT_THRESHOLD: float = 70.0
    DEFAULT_KPI_DEVIATION_THRESHOLD: float = 0.10
    DEFAULT_CONTINGENCY_CAP: float = 100000.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
