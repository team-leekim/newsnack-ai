from fastapi import APIRouter, BackgroundTasks, status
from app.schemas.generation import AIContentCreateRequest, GenerationStatusResponse
from app.services.workflow_service import workflow_service

router = APIRouter(tags=["Content Generation"])

@router.post("/ai-article",
            response_model=GenerationStatusResponse,
            status_code=status.HTTP_202_ACCEPTED)
async def create_ai_article(
    request: AIContentCreateRequest, 
    background_tasks: BackgroundTasks
):
    background_tasks.add_task(workflow_service.run_ai_article_pipeline, request.source_article_ids)

    return GenerationStatusResponse(
        status="accepted",
        message="콘텐츠 생성 작업이 백그라운드에서 시작되었습니다.",
        processed_count=len(request.source_article_ids)
    )
