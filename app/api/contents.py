from fastapi import APIRouter, BackgroundTasks, status, HTTPException
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
        409: {"description": "중복 요청된 이슈가 존재하는 경우"}
    }
)
async def create_batch_ai_articles(
    request: AiArticleBatchGenerationRequest,
    background_tasks: BackgroundTasks,
):
    non_pending = workflow_service.check_duplicate_issues(request.issue_ids)

    if non_pending:
        raise HTTPException(
            status_code=409,
            detail=f"중복 요청된 이슈가 존재합니다. issue_id:{non_pending}"
        )

    background_tasks.add_task(workflow_service.run_batch_ai_articles_pipeline, request.issue_ids)

    return GenerationStatusResponse(
        status="accepted",
        message="콘텐츠 생성 작업이 백그라운드에서 시작되었습니다.",
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
