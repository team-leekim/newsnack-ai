from dotenv import load_dotenv
load_dotenv()

from app.engine.graph import create_graph


test_article = {
    "title": "엔비디아, 시총 1위 탈환... 'AI 칩' 독주 체제 굳히나",
    "content": "세계 최대 AI 칩 제조사 엔비디아가 마이크로소프트를 제치고 다시 한번 글로벌 시가총액 1위에 올라섰습니다. 이번 주 발표된 실적에 따르면 엔비디아의 데이터센터 부문 매출은 전년 대비 400% 급증했습니다. 전문가들은 AI 인프라 구축 수요가 여전히 공급을 앞서고 있어 이러한 독주 체제가 당분간 지속될 것으로 보고 있습니다. 반면, 하드웨어 의존도가 너무 높다는 우려의 목소리도 나오고 있습니다.",
}

test_editor = {
    "name": "에디터B",
    "persona_prompt": "아주 친절하고 상냥한 말투를 사용해. 문장 끝에 '~해요!', '~인가요?'를 쓰고 이모지를 적극적으로 사용해줘(예: 😊, ✨). 어려운 뉴스를 친구에게 설명해주듯 따뜻하게 재해석해줘.",
}

app = create_graph()
final_state = app.invoke({
    "raw_article": test_article,
    "editor": test_editor
})

print("--- 최종 결과 ---")
print(f"타입: {final_state['content_type']}")
print(f"요약: {final_state['summary']}")
print(f"대본: {final_state['final_script']}")
print(f"프롬프트: {final_state['image_prompts']}")
