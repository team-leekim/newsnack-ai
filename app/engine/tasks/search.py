import json
import logging
import urllib.parse
from typing import List

import httpx
from langchain_core.tools import tool
from langchain_tavily import TavilySearch

from app.core.config import settings

logger = logging.getLogger(__name__)


@tool("get_company_logo")
async def get_company_logo(company_name: str) -> str:
    """
    기업/브랜드의 로고 이미지 후보 목록을 검색합니다.
    반드시 영어 공식 명칭으로 검색하세요 (예: 'Samsung Electronics', 'Hana Bank').
    여러 후보의 로고 URL이 포함된 JSON 목록이 반환되며, 기사 문맥에 가장 부합하는
    항목의 logo_url을 최종 답변으로 선택해야 합니다.
    """
    search_url = f"https://api.logo.dev/search?q={urllib.parse.quote(company_name)}&strategy=match"
    headers = {"Authorization": f"Bearer {settings.LOGO_DEV_SECRET_KEY}"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(search_url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    # 각 후보에 로고 URL을 미리 구성하여 반환 (퍼블리셔블 키 사용)
                    candidates = [
                        {
                            "name": item.get("name"),
                            "domain": item.get("domain"),
                            "logo_url": (
                                f"https://img.logo.dev/{item.get('domain')}"
                                f"?token={settings.LOGO_DEV_PUBLISHABLE_KEY}&size=800&format=png&fallback=404"
                            )
                        }
                        for item in data[:5]
                        if item.get("domain")
                    ]
                    if candidates:
                        logger.info(f"[get_company_logo] Found {len(candidates)} candidates for: {company_name}")
                        return json.dumps(candidates, ensure_ascii=False)

            logger.warning(f"[get_company_logo] No candidates found for: {company_name}")
            return "TOOL_FAILED: No brand candidates found. Consider trying get_general_image with an English query instead."
        except Exception as e:
            logger.error(f"[get_company_logo] API fetch failed: {e}")
            return f"TOOL_FAILED: Error occurred - {e}. Try a different tool."


@tool("get_person_thumbnail")
async def get_person_thumbnail(person_name: str) -> str:
    """
    유명 인물이나 고유 명사의 위키백과 공식 프로필 사진(썸네일) URL을 가져옵니다.
    뉴스 기사에 등장하는 주요 인물(정치인, 연예인, 운동선수 등) 검색 시 가장 적합합니다.
    이름은 기사에 표기된 그대로 전달하세요. 번역하거나 로마자로 변환하지 마세요.
    """
    headers = {"User-Agent": "Newsnack/1.0 (https://newsnack.site; contact@newsnack.site)"}

    async with httpx.AsyncClient() as client:
        try:
            # 1단계: Wikipedia 검색 API로 정확한 페이지 제목 탐색 (한/영 이름 모두 처리)
            search_resp = await client.get(
                "https://ko.wikipedia.org/w/api.php",
                params={"action": "query", "list": "search", "srsearch": person_name, "srlimit": 1, "format": "json"},
                headers=headers
            )
            if search_resp.status_code != 200:
                logger.warning(f"[get_person_thumbnail] Search API failed for: {person_name} (status: {search_resp.status_code})")
                return "TOOL_FAILED: No Wikipedia thumbnail found. Consider trying get_general_image instead."

            results = search_resp.json().get("query", {}).get("search", [])
            if not results:
                logger.warning(f"[get_person_thumbnail] No search results for: {person_name}")
                return "TOOL_FAILED: No Wikipedia thumbnail found. Consider trying get_general_image instead."

            found_title = results[0]["title"]
            logger.info(f"[get_person_thumbnail] Found page title: '{found_title}' for query: '{person_name}'")

            # 2단계: 정확한 제목으로 summary 조회 → thumbnail 추출
            summary_resp = await client.get(
                f"https://ko.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(found_title)}",
                headers=headers,
                follow_redirects=True
            )
            if summary_resp.status_code == 200:
                data = summary_resp.json()
                if "thumbnail" in data:
                    return data["thumbnail"]["source"]

            logger.warning(f"[get_person_thumbnail] No thumbnail in summary for: {found_title}")
            return "TOOL_FAILED: No Wikipedia thumbnail found. Consider trying get_general_image instead."
        except Exception as e:
            logger.error(f"[get_person_thumbnail] API fetch failed: {e}")
            return f"TOOL_FAILED: Error occurred - {e}. Try a different tool."


@tool("get_general_image")
async def get_general_image(query: str) -> List[str]:
    """
    다른 툴(get_company_logo, get_person_thumbnail)이 TOOL_FAILED를 반환했을 때만 사용하는 폴백 툴입니다.
    아직 웹에서 해당 로고나 인물 사진을 찾을 수 있을 가능성이 있을 때 마지막 시도로 사용합니다.
    """
    tavily_search = TavilySearch(max_results=3, topic="general")

    try:
        result = await tavily_search.ainvoke({
            "query": query,
            "include_images": True
        })

        images = result.get("images", [])
        if not images:
            logger.warning(f"[get_general_image] No images found for: {query}")
            return ["TOOL_FAILED: No general images found for the given query."]
        return images
    except Exception as e:
        logger.error(f"[get_general_image] Tavily fetch failed: {e}")
        return [f"TOOL_FAILED: Error occurred - {e}."]
