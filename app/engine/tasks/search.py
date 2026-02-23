import logging
import urllib.parse
from typing import Optional, List

import httpx
from langchain_core.tools import tool
from langchain_tavily import TavilySearch

from app.core.config import settings

logger = logging.getLogger(__name__)


@tool("get_company_logo")
async def get_company_logo(company_name: str) -> str:
    """
    특정 기업, 브랜드, 앱, 서비스의 고화질 공식 로고 이미지 URL을 검색합니다.
    (예: '삼성전자', '스타벅스', 'Netflix')
    """
    # Brand Search API를 사용하여 기업의 도메인을 찾습니다.
    search_url = f"https://api.logo.dev/search?q={urllib.parse.quote(company_name)}&strategy=match"
    headers = {"Authorization": f"Bearer {settings.LOGO_DEV_SECRET_KEY}"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(search_url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    domain = data[0].get("domain")
                    if domain:
                        # 로고 이미지 URL 구성 (size=800, format=png, 마진 없음)
                        # backend/server-side 호출이므로 URL에 token을 붙여서 바로 다운로드 가능하게 함
                        return f"https://img.logo.dev/{domain}?token={settings.LOGO_DEV_SECRET_KEY}&size=800&format=png&fallback=404"
            
            return "No company logo found for the given name."
        except Exception as e:
            logger.error(f"[get_company_logo] API fetch failed: {e}")
            return f"Error occurred while searching for company logo: {e}"


@tool("get_person_thumbnail")
async def get_person_thumbnail(person_name: str) -> str:
    """
    유명 인물이나 고유 명사의 위키백과 공식 프로필 사진(썸네일) URL을 가져옵니다.
    뉴스 기사에 등장하는 주요 인물(정치인, 연예인, 운동선수 등) 검색 시 가장 적합합니다.
    """
    url = f"https://ko.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(person_name)}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, follow_redirects=True)
            if response.status_code == 200:
                data = response.json()
                if "thumbnail" in data:
                    return data["thumbnail"]["source"]
            return "No Wikipedia thumbnail found for the given name."
        except Exception as e:
            logger.error(f"[get_person_thumbnail] API fetch failed: {e}")
            return f"Error occurred while searching for person thumbnail: {e}"


@tool("get_general_image")
async def get_general_image(query: str) -> List[str]:
    """
    특정 기업의 로고나 위키백과 인물 사진이 아닌 일반적인 추상 개념, 사건, 사물 사진을 검색할 때 사용합니다.
    (예: '자율주행 자동차', '태풍 피해 현장')
    Tavily 검색 엔진을 통해 관련 이미지 URL 목록을 반환합니다.
    """
    # Tavily Search 래퍼 초기화 (이미지 포함 검색)
    tavily_search = TavilySearch(max_results=3, topic="general")
    
    try:
        # include_images 파라미터는 invoke로 동적 주입
        result = await tavily_search.ainvoke({
            "query": query,
            "include_images": True
        })
        
        images = result.get("images", [])
        if not images:
            return ["No general images found."]
        return images
    except Exception as e:
        logger.error(f"[get_general_image] Tavily fetch failed: {e}")
        return [f"Error occurred while searching for general image: {e}"]
