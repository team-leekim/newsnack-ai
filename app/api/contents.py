from fastapi import APIRouter, BackgroundTasks, status
from app.schemas.generation import AiArticleBatchGenerationRequest, GenerationStatusResponse
from app.services.workflow_service import workflow_service

router = APIRouter(tags=["Content Generation"])


@router.post(
    "/ai-articles",
    summary="AI 기사 일괄 생성",
    description="여러 이슈 ID에 해당하는 콘텐츠를 배치로 생성합니다.",
    response_model=GenerationStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        409: {"description": "해당 이슈에 대한 중복 요청"}
    }
)
async def create_batch_ai_articles(
    request: AiArticleBatchGenerationRequest,
    background_tasks: BackgroundTasks,
):

    background_tasks.add_task(workflow_service.run_batch_ai_articles_pipeline, request.issue_ids)

    return GenerationStatusResponse(
        status="accepted",
        message="콘텐츠 생성 작업이 백그라운드에서 시작되었습니다.",
    )

@router.post("/today-newsnack",
            summary="오늘의 뉴스낵 생성",
            description="오늘의 뉴스낵 콘텐츠를 생성하는 백그라운드 작업을 시작합니다.",
            response_model=GenerationStatusResponse,
            status_code=status.HTTP_202_ACCEPTED)
async def create_today_newsnack(background_tasks: BackgroundTasks):
    background_tasks.add_task(workflow_service.run_today_newsnack_pipeline)
    
    return GenerationStatusResponse(
        status="accepted",
        message="오늘의 뉴스낵 생성 작업이 백그라운드에서 시작되었습니다."
    )
