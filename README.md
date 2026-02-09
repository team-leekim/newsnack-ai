# 뉴스낵 AI 서버

뉴스낵의 AI 콘텐츠 생성을 담당하는 FastAPI 서버입니다. LangGraph 기반 워크플로로 AI 기사(웹툰/카드뉴스)와 오늘의 뉴스낵 브리핑을 자동 생성하며, 완성된 이미지와 오디오는 S3에, 메타데이터는 PostgreSQL(RDS)에 저장합니다.

## 주요 기능

- 외부 파이프라인에서 API 호출로 AI 기사/브리핑 생성
- 이슈별 AI 기사 생성(웹툰 또는 카드뉴스)
- 오늘의 뉴스낵(Top 5 오디오 브리핑) 생성
- 멀티 프로바이더 지원: Google, OpenAI 사용 가능

## 기술 스택

[![FastAPI]][FastAPI url]
[![LangGraph]][LangGraph url]
[![LangChain]][LangChain url]
[![Google Gemini]][Google Gemini url]
[![OpenAI]][OpenAI url]
[![PostgreSQL]][PostgreSQL url]
[![AWS S3]][AWS S3 url]
[![Python]][Python url]

## 동작 방식

1. 외부 파이프라인(예: Airflow)이 이 서버의 API를 호출합니다.
2. AI 기사 생성 워크플로가 이슈 단위로 실행됩니다.
3. 뉴스낵 브리핑 워크플로는 하루 2회(아침/저녁) 자동 실행됩니다.
4. 생성된 미디어는 S3에 업로드되고, 메타데이터는 데이터베이스에 저장됩니다.

## 아키텍처

> 외부 오케스트레이션 시스템과 AI 서버의 관계

```mermaid
sequenceDiagram
    participant Scheduler as 외부 오케스트레이션(Airflow 등)
    participant API as FastAPI AI 서버
    participant Graph as LangGraph 워크플로
    participant LLM as Gemini/OpenAI
    participant S3 as Amazon S3
    participant DB as PostgreSQL(RDS)

    Scheduler->>API: POST /ai-articles
    API->>Graph: AI 기사 워크플로 실행
    Graph->>LLM: 기사 분석/본문/프롬프트 생성
    Graph->>LLM: 이미지 생성
    Graph->>S3: 이미지 업로드
    Graph->>DB: ai_article 저장

    Scheduler->>API: POST /today-newsnack
    API->>Graph: 오늘의 뉴스낵 워크플로 실행
    Graph->>LLM: 브리핑 대본 생성
    Graph->>LLM: TTS 오디오 생성
    Graph->>S3: 오디오 업로드
    Graph->>DB: today_newsnack 저장
```

## 워크플로우

### AI 기사 생성 플로우

> LangGraph StateGraph로 구현된 이슈별 AI 기사 생성 워크플로

```mermaid
graph TD
    Start[시작] --> Analyze[뉴스 분석<br/>analyze_article_node]
    Analyze --> |제목/요약/타입 결정| SelectEditor[에디터 선정<br/>select_editor_node]
    SelectEditor --> |카테고리 매칭 or 랜덤| Branch{콘텐츠 타입}
    
    Branch --> |WEBTOON| Webtoon[웹툰 본문 생성<br/>webtoon_creator_node]
    Branch --> |CARD_NEWS| CardNews[카드뉴스 본문 생성<br/>card_news_creator_node]
    
    Webtoon --> |본문 + 이미지 프롬프트 4개| ImageGen[이미지 생성<br/>image_gen_node]
    CardNews --> |본문 + 이미지 프롬프트 4개| ImageGen
    
    ImageGen --> |병렬 생성 전략| ImageStrategy{프로바이더}
    ImageStrategy --> |OpenAI| OpenAI[4장 전면 병렬 생성]
    ImageStrategy --> |Google + 참조 O| GoogleRef[1장 생성 후<br/>3장 참조 병렬 생성]
    ImageStrategy --> |Google + 참조 X| GoogleNoRef[4장 전면 병렬 생성]
    
    OpenAI --> Save[DB 저장<br/>save_ai_article_node]
    GoogleRef --> Save
    GoogleNoRef --> Save
    
    Save --> |ai_article + reaction_count<br/>issue.is_processed = true| End[종료]
```

**주요 노드 설명:**
- `analyze_article_node`: 원본 기사 분석, 제목/요약 생성, 콘텐츠 타입(웹툰/카드뉴스) 결정
- `select_editor_node`: 이슈의 카테고리와 일치하는 에디터 배정 (없으면 랜덤)
- `webtoon_creator_node` / `card_news_creator_node`: 에디터 페르소나 기반 본문 작성 및 이미지 프롬프트 4개 생성
- `image_gen_node`: 프로바이더별 이미지 생성 전략 실행
  - OpenAI: 4장 전면 병렬 생성
  - Google (참조 O): 1장 기준 이미지 생성 후 나머지 3장을 참조해 병렬 생성
  - Google (참조 X): 4장 전면 병렬 생성
- `save_ai_article_node`: ai_article 테이블 저장, reaction_count 초기화, 이슈 처리 상태 업데이트

### 오늘의 뉴스낵 브리핑 플로우

> 화제성 높은 기사 5개를 선별해 하나의 오디오 브리핑으로 생성

```mermaid
graph TD
    Start[시작] --> Select[대상 기사 선정<br/>select_hot_articles_node]
    Select --> |최근 처리된 이슈 중<br/>화제성 Top 5| Assemble[브리핑 대본 생성<br/>assemble_briefing_node]
    Assemble --> |5개 기사 대본 병합| Audio[오디오 생성<br/>generate_audio_node]
    Audio --> |TTS + 타임라인 계산| AudioStrategy{프로바이더}
    
    AudioStrategy --> |OpenAI| OpenAITTS[OpenAI TTS]
    AudioStrategy --> |Google| GoogleTTS[Gemini TTS]
    
    OpenAITTS --> Save[DB 저장<br/>save_today_newsnack_node]
    GoogleTTS --> Save
    
    Save --> |today_newsnack<br/>audio_url + briefing_articles| End[종료]
```

**주요 노드 설명:**
- `select_hot_articles_node`: 최근 시간 윈도우 내 이슈 중 원본 기사 수가 많은 순으로 5개 선정 (부족 시 최신 AI 기사로 보충)
- `assemble_briefing_node`: 5개 기사를 구조화된 대본으로 변환
- `generate_audio_node`: 대본을 하나로 병합 후 TTS 생성, 오디오 길이 측정 및 타임라인 계산
- `save_today_newsnack_node`: S3 업로드 및 today_newsnack 테이블 저장

## 시스템 구성

- **API**: FastAPI를 통한 HTTP 인터페이스
- **워크플로**: LangGraph로 구현된 AI 기사/브리핑 생성 그래프
- **생성 노드**: 기사 분석 → 에디터 선택 → 본문 작성 → 이미지/오디오 생성 → DB 저장
- **저장소**: S3 미디어 저장소 + PostgreSQL 메타데이터
- **프로바이더**: 환경 변수로 Google Gemini/OpenAI 자유롭게 전환

## 호출 방식

이 서버의 핵심 역할은 외부 파이프라인의 요청을 받아 콘텐츠를 생성하는 것입니다. 뉴스 수집, 이슈 집계, 스케줄링은 모두 외부 시스템에서 수행하며, 다음의 두 엔드포인트로 호출됩니다.

- 이슈 단위 기사 생성: `POST /ai-articles`
- 오늘의 뉴스낵 생성: `POST /today-newsnack`

Swagger 문서는 <http://localhost:8000/docs> 에서 확인할 수 있습니다.

## 환경 변수

필수:
- `API_KEY`: 요청 헤더 `X-API-KEY` 검증용
- `DB_URL`: PostgreSQL 연결 문자열
- `AWS_REGION`, `AWS_S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

AI 프로바이더:
- `AI_PROVIDER`: `google`(기본) 또는 `openai`
- `GOOGLE_API_KEY` (AI_PROVIDER=google일 때 필수)
- `OPENAI_API_KEY` (AI_PROVIDER=openai일 때 필수)

모델 설정(선택):
- `GOOGLE_CHAT_MODEL`, `OPENAI_CHAT_MODEL`
- `GOOGLE_IMAGE_MODEL`, `GOOGLE_IMAGE_MODEL_WITH_REFERENCE`, `OPENAI_IMAGE_MODEL`
- `GOOGLE_TTS_MODEL`, `OPENAI_TTS_MODEL`

## 로컬 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## 참고

- 프로바이더 전환: `AI_PROVIDER=openai`
- 참조 이미지 모드: `GOOGLE_IMAGE_WITH_REFERENCE=true`

<!-- MARKDOWN LINKS & IMAGES -->
[FastAPI]: https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white
[FastAPI url]: https://fastapi.tiangolo.com/
[LangGraph]: https://img.shields.io/badge/langgraph-1C3C3C?style=for-the-badge&logo=langgraph&logoColor=white
[LangGraph url]: https://www.langchain.com/langgraph/
[LangChain]: https://img.shields.io/badge/langchain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white
[LangChain url]: https://www.langchain.com/
[Google Gemini]: https://img.shields.io/badge/google%20gemini-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white
[Google Gemini url]: https://ai.google.dev/gemini-api/docs/
[OpenAI]: https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white
[OpenAI url]: https://openai.com/
[PostgreSQL]: https://img.shields.io/badge/PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white
[PostgreSQL url]: https://www.postgresql.org/
[AWS S3]: https://img.shields.io/badge/AWS%20S3-FF9900?style=for-the-badge&logo=amazon-s3&logoColor=white
[AWS S3 url]: https://aws.amazon.com/s3/
[Python]: https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white
[Python url]: https://www.python.org/
