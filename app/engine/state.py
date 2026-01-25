from typing import TypedDict, List, Optional, Literal
from pydantic import BaseModel, Field

class ArticleState(TypedDict):
    # 입력 데이터
    raw_article: dict
    editor: Optional[dict]
    
    # 분석 단계 결과
    summary: List[str]
    keywords: List[str]
    content_type: str
    
    # 생성 단계 결과
    final_title: str
    final_body: str
    image_prompts: List[str]
    image_urls: List[str]  # 로컬 저장 경로 또는 S3 URL
    current_image_index: int  # 현재 몇 번째 이미지를 생성 중인지 (0~3)

    error: Optional[str]


class AnalysisResponse(BaseModel):
    """뉴스 분석 및 분류 결과"""
    summary: List[str] = Field(description="핵심 요약 3줄 리스트")
    keywords: List[str] = Field(description="뉴스 핵심 키워드 리스트 (최대 5개)")
    content_type: Literal["WEBTOON", "CARD_NEWS"] = Field(description="콘텐츠 타입 분류")


class EditorContentResponse(BaseModel):
    """에디터가 재작성한 본문 및 이미지 프롬프트"""
    final_title: str = Field(description="에디터 말투가 반영된 새로운 제목")
    final_body: str = Field(description="에디터 말투로 재작성된 전체 본문 내용")
    image_prompts: List[str] = Field(description="본문을 시각화할 이미지 생성 영문 프롬프트 4개")
