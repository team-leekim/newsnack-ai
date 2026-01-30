import openai
from google import genai
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings

class AIProviderFactory:

    def __init__(self):
        self._google_client = None
        self._openai_client = None
    
    def get_llm(self, temperature: float = 0.7):
        """환경 변수에 설정된 프로바이더에 맞는 LLM 객체 반환"""
        if settings.AI_PROVIDER == "openai":
            return ChatOpenAI(
                model=settings.OPENAI_CHAT_MODEL,
                openai_api_key=settings.OPENAI_API_KEY,
                temperature=temperature
            )
        else:
            return ChatGoogleGenerativeAI(
                model=settings.GOOGLE_CHAT_MODEL,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=temperature
            )

    def get_image_client(self):
        """환경 변수에 설정된 프로바이더에 맞는 이미지 생성 클라이언트 반환"""
        if settings.AI_PROVIDER == "openai":
            if not self._openai_client:
                self._openai_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            return self._openai_client
        else:
            if not self._google_client:
                self._google_client = genai.Client(api_key=settings.GOOGLE_API_KEY)
            return self._google_client

    def get_audio_client(self):
        """오디오 처리를 위한 클라이언트 반환"""
        if settings.AI_PROVIDER == "openai":
            if not self._openai_client:
                self._openai_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            return self._openai_client
        else:
            # TODO: Google TTS 도입 시 추가
            return None

# 인스턴스 하나만 생성해서 공유
ai_factory = AIProviderFactory()
