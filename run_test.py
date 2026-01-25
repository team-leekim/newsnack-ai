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

print("AI 이미지 생성 완료")
