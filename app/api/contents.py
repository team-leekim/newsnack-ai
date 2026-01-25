from fastapi import APIRouter, BackgroundTasks, Query, status
from app.schemas.generation import GenerationStatusResponse
from app.services.workflow_service import workflow_service

router = APIRouter(tags=["Content Generation"])

@router.post("/ai-article",
            response_model=GenerationStatusResponse,
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
