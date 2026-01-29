from typing import TypedDict, List, Optional, Literal, Any
from pydantic import BaseModel, Field

class ArticleState(TypedDict):
    # 시스템 주입
    db_session: Any # SQLAlchemy Session
    
    content_key: str 

    # 입력 데이터
    issue_id: int
    category_name: str
    raw_article_context: str # 합쳐진 본문
    raw_article_title: str
    
    # 중간 산출물
    editor: Optional[dict] # DB Editor 객체를 Dict로 변환해서 저장
    summary: List[str]
    content_type: str
    
    # 최종 결과
    final_title: str
    final_body: str
    image_prompts: List[str]
    image_urls: List[str]


class AnalysisResponse(BaseModel):
    """뉴스 분석 및 분류 결과"""
    summary: List[str] = Field(description="핵심 요약 3줄 리스트")
    content_type: Literal["WEBTOON", "CARD_NEWS"] = Field(description="콘텐츠 타입 분류")


class EditorContentResponse(BaseModel):
    """에디터가 재작성한 본문 및 이미지 프롬프트"""
    final_title: str = Field(description="에디터 말투가 반영된 새로운 제목")
    final_body: str = Field(description="에디터 말투로 재작성된 전체 본문 내용")
    image_prompts: List[str] = Field(
        min_items=4,
        max_items=4,
        description=(
            "4 distinct visual descriptions in English that form a narrative flow of the news. "
            "Each prompt must describe a unique composition, subject, or perspective to ensure "
            "visual variety and avoid repetitive scenes."
        )
)
