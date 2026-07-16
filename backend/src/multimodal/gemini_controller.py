# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may
# obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from fastapi import APIRouter, Depends, HTTPException, status

from src.auth.auth_guard import RoleChecker
from src.multimodal.dto.gemini_prompt_enhancer_dto import (
    RandomPromptRequestDto,
    RewritePromptRequestDto,
    RewrittenOrRandomPromptResponse,
    DocsChatRequestDto,
    DocsChatResponseDto,
    FeedbackRequestDto,
    FeedbackResponseDto,
    NicoleChatRequestDto,
    NicoleChatResponseDto,
)
from src.multimodal.gemini_service import GeminiService
from src.users.user_model import UserRoleEnum

router = APIRouter(
    prefix="/api/gemini",
    tags=["Gemini APIs"],
    responses={404: {"description": "Not found"}},
    dependencies=[
        Depends(
            RoleChecker(
                allowed_roles=[
                    UserRoleEnum.ADMIN,
                    UserRoleEnum.USER,
                ],
            ),
        ),
    ],
)


@router.post(
    "/rewrite-prompt",
    response_model=RewrittenOrRandomPromptResponse,
    summary="Rewrite and enhance a prompt for image generation",
)
async def rewrite_prompt_endpoint(
    rewrite_request: RewritePromptRequestDto,
    gemini_service: GeminiService = Depends(),
):
    """Takes a set of image generation parameters and combines them into a single,
    high-quality, natural language prompt suitable for an image model.
    This uses a deterministic, rule-based approach.
    """
    try:
        rewritten_prompt = gemini_service.generate_random_or_rewrite_prompt(
            rewrite_request.target_type,
            rewrite_request.user_prompt,
        )
        return RewrittenOrRandomPromptResponse(prompt=rewritten_prompt)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during prompt rewriting: {e}",
        )


@router.post(
    "/random-prompt",
    response_model=RewrittenOrRandomPromptResponse,
    summary="Generate a random, creative prompt for image creation",
)
async def random_prompt_endpoint(
    random_request: RandomPromptRequestDto,
    gemini_service: GeminiService = Depends(),
):
    """Generates a completely new, random, and visually descriptive prompt using Gemini.
    Useful for sparking creativity or for a "surprise me" feature.
    """
    try:
        random_prompt = gemini_service.generate_random_or_rewrite_prompt(
            random_request.target_type,
        )
        return RewrittenOrRandomPromptResponse(prompt=random_prompt)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate random prompt from Gemini: {e}",
        )


@router.post(
    "/docs-chat",
    response_model=DocsChatResponseDto,
    summary="Chat with the AI documentation agent",
)
async def docs_chat_endpoint(
    chat_request: DocsChatRequestDto,
    gemini_service: GeminiService = Depends(),
):
    """Provides interactive Q&A capabilities about project guidelines,
    setup instructions, Flow smart contracts, and Base Mainnet details.
    """
    try:
        reply = gemini_service.docs_agent_chat(
            message=chat_request.message,
            history=chat_request.history,
        )
        return DocsChatResponseDto(response=reply)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to communicate with Docs Chat Agent: {e}",
        )


@router.post(
    "/feedback",
    response_model=FeedbackResponseDto,
    summary="Record developer testing feedback and bug reports",
)
async def feedback_endpoint(
    feedback_request: FeedbackRequestDto,
    gemini_service: GeminiService = Depends(),
):
    """Logs testing comments, bug descriptions, and active pages

    directly to ERROR_LOG.md and Google Cloud Logging.
    """
    try:
        gemini_service.record_developer_feedback(
            message=feedback_request.message,
            url=feedback_request.url,
            timestamp=feedback_request.timestamp,
        )
        return FeedbackResponseDto(status="success")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record developer feedback: {e}",
        )


@router.post(
    "/nicole-chat",
    response_model=NicoleChatResponseDto,
    summary="Chat with NICOLE, the sovereign Gnostic intelligence of ANW Foundations",
)
async def nicole_chat_endpoint(
    req: NicoleChatRequestDto,
    gemini_service: GeminiService = Depends(),
):
    """Interact with the NICOLE Gnostic Oracle using custom Solfeggio frequency parameters,

    ancient language roots, and tailored depth levels.
    """
    try:
        response_text = gemini_service.nicole_oracle_chat(
            message=req.message,
            history=req.history,
            frequency=req.frequency,
            language=req.language,
            depth=req.depth,
        )
        return NicoleChatResponseDto(response=response_text)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"NICOLE Oracle was unable to formulate a revelation: {e}",
        )

