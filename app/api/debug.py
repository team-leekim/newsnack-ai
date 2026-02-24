from fastapi import APIRouter, HTTPException
from app.schemas.generation import ImageResearchDebugResponse
from app.services.debug_service import debug_service

router = APIRouter(tags=["Debug"])


@router.get(
    "/ai-articles/debug/image-research/{issue_id}",
    summary="[DEBUG] 이미지 리서치 에이전트 단독 테스트",
    description="이슈 ID에 대해 분석과 이미지 리서치 단계만 실행합니다. DB 상태를 변경하지 않습니다.",
    response_model=ImageResearchDebugResponse,
)
async def debug_image_research(issue_id: int):
    try:
        result = await debug_service.run_image_research_debug(issue_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/ai-articles/debug/image-research-and-validate/{issue_id}",
    summary="[DEBUG] 이미지 리서치 + 검증 노드 단독 테스트",
    description="이슈 ID에 대해 분석과 이미지 리서치, 이미지 검증 단계만 실행합니다. DB 상태를 변경하지 않습니다.",
    response_model=ImageResearchDebugResponse,
)
async def debug_image_research_and_validate(issue_id: int):
    try:
        result = await debug_service.run_image_research_and_validate_debug(issue_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
