from typing import TypedDict, List, Optional, Literal
from pydantic import BaseModel, Field

class GraphState(TypedDict):
    # 입력 데이터
    raw_article: dict
    editor: dict
    
    # 중간 결과물
    summary: List[str]      # 3줄 요약
    content_type: str       # WEBTOON | CARD_NEWS
    
    # 최종 결과물
    final_script: str       # 에디터 말투로 변환된 본문
    image_prompts: List[str] # 각 장면별 이미지 생성 프롬프트
    
    # 상태 관리용
    error: Optional[str]


class AnalysisResponse(BaseModel):
    """뉴스 분석 결과 (요약 및 타입 분류)"""
    summary: List[str] = Field(description="뉴스 핵심 내용을 3줄로 요약한 리스트")
    content_type: Literal["WEBTOON", "CARD_NEWS"] = Field(
        description="뉴스의 성격에 따른 콘텐츠 타입 (스토리 위주면 WEBTOON, 정보 위주면 CARD_NEWS)"
    )


class ImagePromptResponse(BaseModel):
    """장면별 이미지 생성 프롬프트 리스트"""
    prompts: List[str] = Field(description="이미지 생성을 위한 영문 프롬프트 4개 리스트")
