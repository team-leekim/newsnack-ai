import json
from dotenv import load_dotenv
load_dotenv()

from app.engine.graph import create_graph


# 뉴스 데이터 로드
with open("data/raw_articles.json", "r", encoding="utf-8") as f:
    articles = json.load(f)

app = create_graph()

final_state = app.invoke({
    "raw_article": articles[0],
    "editor": None
})

print(f"\n[1] 분석 결과")
print(f"- 분류된 타입: {final_state['content_type']}")
print(f"- 추출된 키워드: {final_state['keywords']}")

print(f"\n[2] 배정된 에디터")
print(f"- 에디터 이름: {final_state['editor']['name']}")
print(f"- 에디터 타입: {final_state['editor']['type']}")

print(f"\n[3] 최종 콘텐츠 (제목: {final_state['final_title']})")
print(f"- 본문 내용 샘플: {final_state['final_body'][:100]}...")
print(f"- 이미지 프롬프트: {final_state['image_prompts']}")
