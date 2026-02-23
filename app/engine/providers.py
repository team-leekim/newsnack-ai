import openai
from google import genai
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings


class AiProviderFactory:
    def __init__(self):
        self._google_client = None
        self._openai_client = None
        self._google_chat_model = None
        self._openai_chat_model = None

    def _get_google_client(self):
        if not self._google_client:
            self._google_client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        return self._google_client

    def _get_openai_client(self):
        if not self._openai_client:
            self._openai_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._openai_client

    def _get_google_chat_model(self):
        if not self._google_chat_model:
            self._google_chat_model = ChatGoogleGenerativeAI(
                model=settings.GOOGLE_CHAT_MODEL,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=0.7
            )
        return self._google_chat_model

    def _get_openai_chat_model(self):
        if not self._openai_chat_model:
            self._openai_chat_model = ChatOpenAI(
                model=settings.OPENAI_CHAT_MODEL,
                openai_api_key=settings.OPENAI_API_KEY,
                temperature=0.7
            )
        return self._openai_chat_model

    def get_chat_model(self):
        """환경 변수에 설정된 프로바이더에 맞는 Chat Model 반환"""
        if settings.AI_PROVIDER == "openai":
            return self._get_openai_chat_model()
        else:
            return self._get_google_chat_model()

    def get_image_client(self):
        """이미지 생성용 클라이언트 반환"""
        if settings.AI_PROVIDER == "openai":
            return self._get_openai_client()
        else:
            return self._get_google_client()

    def get_audio_client(self):
        """오디오 생성용 클라이언트 반환"""
        if settings.AI_PROVIDER == "openai":
            return self._get_openai_client()
        else:
            return self._get_google_client()


# 전역 인스턴스 생성
ai_factory = AiProviderFactory()
