from langchain_core.prompts import ChatPromptTemplate


# ============================================================================
# 기사 분석 프롬프트
# ============================================================================

ARTICLE_ANALYSIS_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", """당신은 뉴스 큐레이션 전문가입니다. 다음 뉴스를 분석하여 제목을 최적화하고 내용을 요약하세요.

[작업 가이드라인]
1. 제목(title): 
   - 원본 제목과 본문 내용을 바탕으로 기사의 **핵심 내용을 가장 잘 나타내는 짧고 간결한 제목**을 생성할 것.
   - **최대 15자 내외**로 작성하여 한눈에 들어오도록 할 것.
   - 독자의 흥미를 유발하되, **과장 없이 명확한 키워드**를 포함할 것.
   - 문체를 변경하거나 감정을 섞지 말고, **객관적인 언론사 기사 제목**처럼 작성할 것.

2. 요약(summary):
   - 반드시 3줄로 작성할 것.
   - 핵심 위주로 아주 짧고 간결하게 작성할 것.
   - 문장 끝을 '~함', '~임', '~함'과 같은 명사형 어미로 끝낼 것. (예: 삼성전자 실적 발표함, 금리 인상 결정됨)

3. 분류(content_type):
   [WEBTOON 기준 - 스토리와 드라마에 초점]
   - 시간 흐름이 명확한 서사 구조 (과거→현재→향후)
   - 인물의 극적인 행동, 결단, 대응 과정
   - 갈등, 반전, 감정 요소가 두드러짐
   - "무슨 일이 벌어졌는가"가 핵심
   - 예: 논란 전개 과정, 운동선수의 극적 성과, 사건의 반전, 인물의 결단과 대응
   
   [CARD_NEWS 기준 - 정보와 설명에 초점]
   - 정책, 제도, 서비스, 기술에 대한 설명 또는 소개
   - 수치, 데이터, 통계를 활용한 비교 또는 분석
   - 단순 발표, 인사 소식, 행정 뉴스
   - "무엇인가, 어떻게 작동하는가"가 핵심
   - 예: 신규 서비스 소개, 정책 발표, 기술 동향, 경제 지표, 인사 발표
   
   ⚠️ 판단 기준: 스토리텔링 요소가 강하면 WEBTOON, 정보 전달이 주목적이면 CARD_NEWS"""),
    ("human", """[분석 대상]
원본 제목: {original_title}
본문 내용: {content}

[출력 요구사항]
- title: 최적화된 제목
- summary: 명사형 어미를 사용한 3줄 요약
- content_type: 분류 결과"""),
])


# ============================================================================
# 콘텐츠 생성 프롬프트 (System 부분)
# ============================================================================

WEBTOON_SYSTEM_PROMPT = """너는 지금부터 이 뉴스를 4페이지 분량의 시각적 스토리보드로 재구성해야 해.

[미션]
1. 각 페이지의 'image_prompts'는 서로 다른 시각적 구도와 내용을 담아야 함.
2. 1~4번이 하나의 흐름을 갖되, 시각적으로 중복되는 장면(동일한 각도나 반복되는 구도)은 절대 피할 것.
3. 각 장면의 배경, 인물의 위치, 카메라의 거리를 AI가 서사에 맞춰 자유롭고 역동적으로 구성해줘."""

CARD_NEWS_SYSTEM_PROMPT = """너는 복잡한 뉴스를 한눈에 들어오는 4장의 카드뉴스로 재구성해야 해.

[미션]
1. 4개의 'image_prompts'는 뉴스 본문의 핵심 정보를 단계별로 시각화해야 함.
2. 각 페이지는 시각적 중복을 피하기 위해 레이아웃을 다르게 구성해:
   - 1번: 시선을 끄는 강력한 제목과 상징적인 아이콘
   - 2번: 핵심 수치나 데이터를 강조하는 차트 또는 다이어그램
   - 3번: 사건의 인과관계를 보여주는 단계별 레이아웃
   - 4번: 한눈에 들어오는 요약 리스트와 마무리 비주얼
3. 모든 설명은 한국어로 작성하되, 'image_prompts' 내의 시각 묘사만 영어로 작성해줘.
4. 디자인은 세련된 소셜 미디어 감성(Modern and trendy social media aesthetic)을 유지해."""


# ============================================================================
# 템플릿 생성 헬퍼 함수 (동적 persona 처리)
# ============================================================================

def create_webtoon_template(persona_prompt: str) -> ChatPromptTemplate:
    """
    에디터의 페르소나를 포함한 웹툰 콘텐츠 생성 템플릿 생성
    
    Args:
        persona_prompt: 에디터의 페르소나 프롬프트
        
    Returns:
        구성된 ChatPromptTemplate 객체
    """
    return ChatPromptTemplate.from_messages([
        ("system", f"{persona_prompt}\n{WEBTOON_SYSTEM_PROMPT}"),
        ("human", "제목: {title}\n내용: {content}"),
    ])


def create_card_news_template(persona_prompt: str) -> ChatPromptTemplate:
    """
    에디터의 페르소나를 포함한 카드뉴스 콘텐츠 생성 템플릿 생성
    
    Args:
        persona_prompt: 에디터의 페르소나 프롬프트
        
    Returns:
        구성된 ChatPromptTemplate 객체
    """
    return ChatPromptTemplate.from_messages([
        ("system", f"{persona_prompt}\n{CARD_NEWS_SYSTEM_PROMPT}"),
        ("human", "제목: {title}\n내용: {content}"),
    ])


# ============================================================================
# 브리핑 스크립트 생성 프롬프트
# ============================================================================

BRIEFING_SYSTEM_PROMPT = """당신은 '뉴스낵(newsnack)'의 메인 마스코트인 '박수박사수달'입니다.
아나운서로서 뉴스 기사들을 자연스럽게 브리핑하는 대본을 작성합니다.

[아나운서 페르소나 가이드]
1. 말투: 20대 후반의 활기차고 지적인 친구 같은 느낌. (~해요, ~네요 문체 사용)
2. 성격: 뉴스를 전하는 게 너무 즐거운 에너지 넘치는 수달.
3. 특징: 
   - 오프닝: "안녕하세요! 오늘의 뉴스낵을 시작할게요."처럼 밝게 시작.
   - 클로징: "오늘 소식은 여기까지예요. 오늘도 즐거운 하루 보내세요!" 등 인사.
   - 각 기사 대본 사이에 자연스러운 연결 멘트(브릿지)를 포함할 것.

[작성 규칙]
1. 반드시 입력된 기사 순서와 동일하게 모든 대본 세그먼트를 생성할 것.
2. 각 기사당 150-200자 내외(약 30초)의 분량으로 작성할 것.
3. 각 기사의 핵심 정보는 반드시 포함하되, 에디터의 개별 말투는 지우고 '박수박사수달'의 톤으로 재창조할 것.
4. 전문 용어는 최대한 쉽게 풀어서 설명할 것."""


def create_briefing_template(num_articles: int) -> ChatPromptTemplate:
    """
    기사 개수를 포함한 브리핑 스크립트 생성 템플릿 생성
    
    Args:
        num_articles: 브리핑할 기사의 개수
        
    Returns:
        구성된 ChatPromptTemplate 객체
    """
    return ChatPromptTemplate.from_messages([
        ("system", BRIEFING_SYSTEM_PROMPT),
        ("human", f"""아래 제공된 {num_articles}개의 뉴스 기사 순서대로 브리핑 대본을 작성하세요.

[뉴스 데이터]
{{articles}}"""),
    ])


# ============================================================================
# TTS 음성 생성 프롬프트
# ============================================================================

TTS_INSTRUCTIONS = """
A natural, conversational voice of a smart and friendly 'Otter' character in the late 20s. 
The tone is exceptionally bright, energetic, and engaging, like a 'smart friend' enthusiastically explaining an interesting topic. 
Avoid a rigid broadcast style. Use a fluid, melodic intonation with a 'soft and cute' edge, yet remain professional and trustworthy. 
The delivery should be lighthearted, with natural pauses for breath and thought, as if the speaker is genuinely excited about the news. 
Ensure sentence endings are smooth and friendly (not formal or clipped). 
The overall vibe is 'intelligent, approachable, and bubbly'.
"""


def create_tts_prompt(script: str) -> str:
    """
    TTS 음성 생성을 위한 프롬프트 생성
    
    Args:
        script: 읽을 대본 텍스트
        
    Returns:
        TTS API에 전달할 최종 프롬프트
    """
    return f"{TTS_INSTRUCTIONS}\n\n#### TRANSCRIPT\n{script}"


# ============================================================================
# 이미지 생성 스타일 프롬프트
# ============================================================================

class ImageStyle:
    """이미지 생성 스타일 상수 관리"""
    
    WEBTOON = (
        "Modern digital webtoon art style, clean line art, vibrant cel-shading. "
        "Character must have consistent hair and outfit from the reference."
    )
    
    CARD_NEWS = (
        "Minimalist flat vector illustration, Instagram aesthetic, solid pastel background. "
        "Maintain exact same color palette and layout style."
    )
    
    @classmethod
    def get_style(cls, content_type: str) -> str:
        """콘텐츠 타입에 따른 스타일 반환"""
        if content_type == "WEBTOON":
            return cls.WEBTOON
        elif content_type == "CARD_NEWS":
            return cls.CARD_NEWS
        else:
            raise ValueError(f"Unknown content_type: {content_type}")


def create_image_prompt(style: str, prompt: str, language: str = "Korean") -> str:
    """이미지 생성 프롬프트 조합
    
    Args:
        style: 이미지 스타일 (ImageStyle.WEBTOON 또는 ImageStyle.CARD_NEWS)
        prompt: 기본 프롬프트
        language: 텍스트 언어 (기본값: Korean)
    
    Returns:
        최종 이미지 생성 프롬프트
    """
    return f"{style} {prompt}. Ensure all text is in {language} if any."


def create_google_image_prompt(
    style: str,
    prompt: str,
    content_type: str,
    with_reference: bool = False
) -> str:
    """Google Gemini 이미지 생성 전용 프롬프트
    
    Args:
        style: 이미지 스타일
        prompt: 기본 프롬프트
        content_type: 콘텐츠 타입 (WEBTOON/CARD_NEWS)
        with_reference: 참조 이미지 사용 여부
    
    Returns:
        최종 프롬프트
    """
    instruction = (
        "Write all text for Korean readers. "
        "Use Korean for general text, but keep proper nouns, brand names, "
        "and English acronyms in English. Ensure all text is legible."
    )
    
    if content_type == "CARD_NEWS":
        instruction += " Focus on infographic elements and consistent background color."
    
    final_prompt = f"{style} {prompt}. {instruction}"
    
    if with_reference:
        final_prompt += (
            " Use the reference image ONLY to maintain character/style consistency. "
            "IGNORE its composition and pose."
        )
    
    return final_prompt
