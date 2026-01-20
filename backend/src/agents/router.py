from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from src.agents.dto.agent_dto import AgentGenerationRequest, AgentGenerationResponse
from src.agents.agent_service import AgentService
from src.auth.auth_guard import get_current_user
from src.users.user_model import UserModel
from src.common.event_bus import get_event_bus

router = APIRouter(prefix="/api/agents", tags=["Agents"])

@router.post("/generate", response_model=AgentGenerationResponse, status_code=status.HTTP_200_OK)
async def generate_compliant_media(
    request: AgentGenerationRequest,
    agent_service: AgentService = Depends(),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Triggers the Agentic RAG workflow: Enforce -> Generate -> Validate (Async).
    """
    return await agent_service.generate_compliant_media(request, current_user)

@router.get("/events/stream", response_class=StreamingResponse)
async def stream_agent_events(current_user: UserModel = Depends(get_current_user)):
    """
    Streams ADK events for the current user.
    """
    event_bus = get_event_bus()
    return StreamingResponse(
        event_bus.stream_events(f"user_{current_user.email}"),
        media_type="text/event-stream"
    )
