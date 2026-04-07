from pydantic import model_validator
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # PostgreSQL (개별 변수)
    POSTGRES_USER: str = "3dgs"
    POSTGRES_PASSWORD: str = "changeme"
    POSTGRES_DB: str = "3dgs_platform"
    POSTGRES_HOST: str = "postgres"
    DATABASE_URL: str = ""

    # Redis
    REDIS_PASSWORD: str = "changeme"
    REDIS_HOST: str = "redis"
    REDIS_URL: str = ""

    # RabbitMQ
    RABBITMQ_DEFAULT_USER: str = "3dgs"
    RABBITMQ_DEFAULT_PASS: str = "changeme"
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_URL: str = ""

    # MinIO
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_PUBLIC_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "changeme123"
    MINIO_BUCKET: str = "3dgs-platform"
    MINIO_SECURE: bool = False
    MINIO_PUBLIC_SECURE: bool = False

    # JWT
    JWT_SECRET_KEY: str = "changeme"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # Dev mode (bypass Google OAuth)
    DEV_MODE: bool = False

    # Public URL (for OAuth redirect behind reverse proxy)
    PUBLIC_BASE_URL: str = ""

    @model_validator(mode="after")
    def assemble_urls(self) -> "Settings":
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:5432/{self.POSTGRES_DB}"
            )
        if not self.REDIS_URL:
            self.REDIS_URL = f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:6379/0"
        if not self.RABBITMQ_URL:
            self.RABBITMQ_URL = (
                f"amqp://{self.RABBITMQ_DEFAULT_USER}:{self.RABBITMQ_DEFAULT_PASS}"
                f"@{self.RABBITMQ_HOST}:5672//"
            )
        return self

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
