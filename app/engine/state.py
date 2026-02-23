from typing import TypedDict, List, Optional
from sqlalchemy.orm import Session

class AiArticleState(TypedDict):
    # 시스템 주입
    db_session: Session # SQLAlchemy Session
    
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

class TodayNewsnackState(TypedDict):
    db_session: Session
    target_issue_ids: List[int]    # 요청받은 Issue ID 리스트
    selected_articles: List[dict]  # 선정된 기사별 정보
    briefing_segments: List[dict]  # 기사 ID별 생성된 대본
    total_audio_bytes: bytes       # 생성된 오디오 바이너리
    briefing_articles_data: List[dict] # 최종 DB 저장용 타임라인 포함 데이터
