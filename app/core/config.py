from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # 환경 변수 정의
    PROJECT_NAME: str = "newsnack AI Server"
    
    # 필수 환경 변수
    GOOGLE_API_KEY: str
    DATABASE_URL: Optional[str] = None
    AWS_S3_BUCKET: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

settings = Settings()
