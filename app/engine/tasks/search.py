import json
import httpx
import logging
import urllib.parse
from langchain_core.tools import tool

from app.core.config import settings

logger = logging.getLogger(__name__)


@tool("get_company_logo")
async def get_company_logo(company_name_in_english: str) -> str:
    """
    기업/브랜드의 로고 이미지 후보 목록을 검색합니다.
    반드시 영어 공식 명칭(ENGLISH name)으로 검색하세요. 한글은 허용되지 않습니다.

    Args:
        company_name_in_english: 기업/브랜드의 영어 공식 명칭

    Returns:
        JSON 형식의 로고 이미지 후보 목록
    """
    search_url = f"https://api.logo.dev/search?q={urllib.parse.quote(company_name_in_english)}"
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
                        logger.info(f"[get_company_logo] Found {len(candidates)} candidates for: {company_name_in_english}")
                        return json.dumps(candidates, ensure_ascii=False)

            logger.warning(f"[get_company_logo] No candidates found for: {company_name_in_english}")
            return "TOOL_FAILED: No brand candidates found. MUST try get_fallback_image instead."

        except Exception as e:
            logger.error(f"[get_company_logo] API fetch failed: {e}")
            return f"TOOL_FAILED: Error occurred - {e}. MUST try get_fallback_image instead."


@tool("get_person_thumbnail")
async def get_person_thumbnail(person_name: str) -> str:
    """
    유명 인물이나 고유 명사의 위키백과 공식 프로필 사진(썸네일) URL을 가져옵니다.
    뉴스 기사에 등장하는 주요 인물(정치인, 연예인, 운동선수 등) 검색 시 가장 적합합니다.
    이름은 기사에 표기된 그대로 전달하세요. 번역하거나 로마자로 변환하지 마세요.
    반환된 JSON 목록 [{title, description, thumbnail_url}]을 확인하고 기사 문맥에 맞는 인물을 골라 최종 URL을 선택하세요.

    Args:
        person_name: 인물의 이름

    Returns:
        JSON 형식의 인물 썸네일 목록
    """
    headers = {"User-Agent": "Newsnack/1.0 (https://newsnack.site; contact@newsnack.site)"}

    async with httpx.AsyncClient() as client:
        try:
            # 1단계: Wikipedia 검색 API로 상위 5개 페이지 제목 및 설명 탐색
            search_resp = await client.get(
                "https://ko.wikipedia.org/w/api.php",
                params={
                    "action": "query", "list": "search", 
                    "srsearch": person_name, "srlimit": 5, 
                    "srprop": "snippet", "format": "json"
                },
                headers=headers
            )
            if search_resp.status_code != 200:
                logger.warning(f"[get_person_thumbnail] Search API failed for: {person_name} (status: {search_resp.status_code})")
                return "TOOL_FAILED: No Wikipedia page found. MUST try get_fallback_image."

            results = search_resp.json().get("query", {}).get("search", [])
            if not results:
                logger.warning(f"[get_person_thumbnail] No search results for: {person_name}")
                return "TOOL_FAILED: No Wikipedia page found. MUST try get_fallback_image."

            # 2단계: 각 검색 결과의 summary 조회 → 썸네일 추출
            candidates = []
            for res in results:
                title = res["title"]
                snippet = res.get("snippet", "")
                
                summary_resp = await client.get(
                    f"https://ko.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}",
                    headers=headers,
                    follow_redirects=True
                )
                
                if summary_resp.status_code == 200:
                    data = summary_resp.json()
                    if "thumbnail" in data:
                        candidates.append({
                            "title": title,
                            "description": snippet,
                            "thumbnail_url": data["thumbnail"]["source"]
                        })

            if not candidates:
                logger.warning(f"[get_person_thumbnail] No thumbnails found in any search results for: {person_name}")
                return "TOOL_FAILED: No Wikipedia thumbnails found for any candidates. MUST try get_fallback_image."

            logger.info(f"[get_person_thumbnail] Found {len(candidates)} candidates for query: '{person_name}'")
            return json.dumps(candidates, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"[get_person_thumbnail] API fetch failed: {e}")
            return f"TOOL_FAILED: Error occurred - {e}. MUST try get_fallback_image."


@tool("get_fallback_image")
async def get_fallback_image(query: str) -> str:
    """
    다른 툴(get_company_logo, get_person_thumbnail)이 TOOL_FAILED를 반환했을 때 사용하는 최후의 폴백 도구입니다.
    카카오 이미지 검색을 사용하여 국내 로컬 뉴스/기업/인물 이미지를 빠르고 정확하게 찾아냅니다.
    
    [중요 지침]
    - 오직 기사의 **핵심 인물명** 또는 **핵심 기관/기업명**에만 집중하여 검색하세요.
    - 기사의 사건이나 상황(예: "등록 포기", "의회 출석")을 검색어에 절대 포함하지 마세요.
    - 단답형 이름만 단독으로 검색하지 말고, 직업이나 소속과 같은 문맥 단어를 조합하세요.
    - 단, 전체 검색어는 단어 2~3개 내외로 가장 짧고 직관적으로 작성해야 합니다.
      * 인물 검색 예시: "[소속/직업] [인물명]" 또는 "[이름] [직책]" (예: "삼성전자 홍길동", "홍길동 대표")
      * 기관/기업 검색 예시: "[브랜드/기관명] 로고" (예: "삼성 로고")
    - 반환된 JSON은 {image_url, display_sitename, doc_url} 구조를 갖습니다.
    - display_sitename(출처)이 뉴스 매체이거나 신뢰성 있는 블로그인 경우를 우선하여 선택하세요.

    Args:
        query: 검색어

    Returns:
        JSON 형식의 이미지 목록
    """
    if not settings.KAKAO_REST_API_KEY:
        return "TOOL_FAILED: KAKAO_REST_API_KEY is not configured."

    url = "https://dapi.kakao.com/v2/search/image"
    headers = {"Authorization": f"KakaoAK {settings.KAKAO_REST_API_KEY}"}
    params = {"query": query, "size": 5}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            if response.status_code != 200:
                logger.warning(f"[get_fallback_image] Failed to fetch. Status: {response.status_code}")
                return f"TOOL_FAILED: Kakao API returned status {response.status_code}"

            data = response.json()
            documents = data.get("documents", [])
            
            if not documents:
                logger.warning(f"[get_fallback_image] No images found for: {query}")
                return "TOOL_FAILED: No general images found for the given query."

            candidates = [
                {
                    "display_sitename": doc.get("display_sitename", ""),
                    "image_url": doc.get("image_url", ""),
                    "doc_url": doc.get("doc_url", "")
                }
                for doc in documents
            ]
            
            logger.info(f"[get_fallback_image] Found {len(candidates)} image candidates for: {query}")
            return json.dumps(candidates, ensure_ascii=False)

        except Exception as e:
            logger.error(f"[get_fallback_image] Fetch failed: {e}")
            return f"TOOL_FAILED: Error occurred - {e}."
