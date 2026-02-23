from typing import Literal, Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Newsnack AI Server"
    
    # AI Provider
    AI_PROVIDER: Literal["google", "openai"] = "google"

    # AI Models
    GOOGLE_CHAT_MODEL: str = "gemini-2.5-flash-lite"
    OPENAI_CHAT_MODEL: str = "gpt-5-nano"
    GOOGLE_IMAGE_MODEL: str = "gemini-2.5-flash-image"
    GOOGLE_IMAGE_MODEL_WITH_REFERENCE: str = "gemini-3-pro-image-preview"
    GOOGLE_IMAGE_WITH_REFERENCE: bool = True
    OPENAI_IMAGE_MODEL: str = "gpt-image-1.5"
    GOOGLE_TTS_MODEL: str = "gemini-2.5-flash-preview-tts"
    OPENAI_TTS_MODEL: str = "gpt-4o-mini-tts"

    # TTS Settings
    GOOGLE_TTS_VOICE: str = "Achird"
    OPENAI_TTS_VOICE: str = "marin"

    # API Keys
    API_KEY: str
    GOOGLE_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    
    # Database & Storage
    DB_URL: str
    AWS_REGION: str = "ap-northeast-2"
    AWS_S3_BUCKET: str
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str

    # Other Settings
    AI_ARTICLE_MAX_CONCURRENT_GENERATIONS: int = 2
    AI_ARTICLE_GENERATION_DELAY_SECONDS: int = 5
    TODAY_NEWSNACK_ISSUE_TIME_WINDOW_HOURS: int = 14

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
