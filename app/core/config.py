from typing import Literal, Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # 환경 변수 정의
    PROJECT_NAME: str = "newsnack AI Server"
    
    # AI Provider
    AI_PROVIDER: Literal["google", "openai"] = "google"

    # AI Models
    GOOGLE_CHAT_MODEL: str = "gemini-2.5-flash-lite"
    OPENAI_CHAT_MODEL: str = "gpt-5-nano"
    GOOGLE_IMAGE_MODEL: str = "gemini-3-pro-image-preview"
    OPENAI_IMAGE_MODEL: str = "gpt-image-1.5"
    
    # API Keys
    GOOGLE_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    
    # Database & Storage
    DATABASE_URL: Optional[str] = None
    AWS_S3_BUCKET: Optional[str] = None

    @model_validator(mode='after')
    def check_api_keys(self) -> 'Settings':
        if self.AI_PROVIDER == "google" and not self.GOOGLE_API_KEY:
            raise ValueError("AI_PROVIDER가 'google'일 때는 GOOGLE_API_KEY가 필수입니다.")
        if self.AI_PROVIDER == "openai" and not self.OPENAI_API_KEY:
            raise ValueError("AI_PROVIDER가 'openai'일 때는 OPENAI_API_KEY가 필수입니다.")
        return self
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

settings = Settings()
