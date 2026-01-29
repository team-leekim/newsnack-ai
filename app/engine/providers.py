import openai
from google import genai
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings

class AIProviderFactory:
    
    @staticmethod
    def get_llm(temperature: float = 0.7):
        """환경 변수에 설정된 프로바이더에 맞는 LLM 객체 반환"""
        if settings.AI_PROVIDER == "openai":
            return ChatOpenAI(
                model="gpt-5-nano",
                openai_api_key=settings.OPENAI_API_KEY,
                temperature=temperature
            )
        else:
            return ChatGoogleGenerativeAI(
                model="gemini-2.5-flash-lite",
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=temperature
            )

    @staticmethod
    def get_image_client():
        """환경 변수에 설정된 프로바이더에 맞는 이미지 생성 클라이언트 반환"""
        if settings.AI_PROVIDER == "openai":
            # OpenAI 비동기 클라이언트 반환
            return openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        else:
            # Google GenAI 클라이언트 반환
            return genai.Client(api_key=settings.GOOGLE_API_KEY)

# 인스턴스 미리 생성
ai_factory = AIProviderFactory()
