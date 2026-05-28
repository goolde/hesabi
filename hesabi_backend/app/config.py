from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Hesabi API"
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    database_url: str = "sqlite:///./hesabi.db"
    cors_origins: str = "http://localhost:5173,http://localhost:8000"

    class Config:
        env_file = ".env"

settings = Settings()
