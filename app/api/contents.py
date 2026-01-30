from fastapi import APIRouter, BackgroundTasks, Query, status
from app.schemas.generation import GenerationStatusResponse
from app.services.workflow_service import workflow_service

router = APIRouter(tags=["Content Generation"])

@router.post("/ai-article",
            summary="AI 기사 생성",
            description="특정 이슈 ID에 해당하는 콘텐츠를 생성하는 백그라운드 작업을 시작합니다.",            response_model=GenerationStatusResponse,
            status_code=status.HTTP_202_ACCEPTED)
async def create_ai_article(
    background_tasks: BackgroundTasks,
    issue_id: int = Query(..., description="생성할 AI 콘텐츠의 이슈 ID")
):
    background_tasks.add_task(workflow_service.run_ai_article_pipeline, issue_id)

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
