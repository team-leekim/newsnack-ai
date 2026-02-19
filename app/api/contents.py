from fastapi import APIRouter, BackgroundTasks, status, HTTPException
from fastapi.concurrency import run_in_threadpool
from app.schemas.generation import AiArticleBatchGenerationRequest, GenerationStatusResponse, TodayNewsnackRequest
from app.services.workflow_service import workflow_service

router = APIRouter(tags=["Content Generation"])


@router.post(
    "/ai-articles",
    summary="AI 기사 일괄 생성",
    description="여러 이슈 ID에 해당하는 콘텐츠를 배치로 생성합니다.",
    response_model=GenerationStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        409: {"description": "처리 가능한 이슈가 없는 경우"}
    }
)
async def create_batch_ai_articles(
    request: AiArticleBatchGenerationRequest,
    background_tasks: BackgroundTasks,
):
    occupied_ids = await run_in_threadpool(workflow_service.occupy_issues, request.issue_ids)

    if not occupied_ids:
        raise HTTPException(
            status_code=409,
            detail="처리 가능한 이슈가 없습니다."
        )

    background_tasks.add_task(workflow_service.run_batch_ai_articles_pipeline, occupied_ids)

    return GenerationStatusResponse(
        status="accepted",
        message=f"총 {len(request.issue_ids)}개 요청 중 {len(occupied_ids)}개의 콘텐츠 생성이 시작되었습니다.",
    )

@router.post("/today-newsnack",
            summary="오늘의 뉴스낵 생성",
            description="지정된 이슈 ID에 해당하는 AI 기사로 오늘의 뉴스낵 콘텐츠를 생성합니다.",
            response_model=GenerationStatusResponse,
            status_code=status.HTTP_202_ACCEPTED)
async def create_today_newsnack(
    request: TodayNewsnackRequest,
    background_tasks: BackgroundTasks
):
    background_tasks.add_task(workflow_service.run_today_newsnack_pipeline, request.issue_ids)
    
    return GenerationStatusResponse(
        status="accepted",
        message="오늘의 뉴스낵 생성 작업이 백그라운드에서 시작되었습니다."
    )
