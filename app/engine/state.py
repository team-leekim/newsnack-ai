from typing import TypedDict, List, Optional

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
