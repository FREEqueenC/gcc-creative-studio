from typing import List, Optional
from google.adk.agents import LlmAgent
from src.tools.adk_wrappers import create_adk_search_tool
from src.common.vector_search_service import VectorSearchService
from src.multimodal.gemini_service import GeminiService
from src.common.base_dto import GenerationModelEnum
from src.brand_guidelines.repository.brand_guideline_repository import BrandGuidelineRepository

class BrandingEnforcerADK(LlmAgent):
    """
    ADK Agent for interpreting and enforcing brand guidelines.
    """
    
    def __init__(
        self,
        name: str,
        vector_search_service: VectorSearchService,
        gemini_service: GeminiService,
        brand_guideline_repo: BrandGuidelineRepository,
        model: GenerationModelEnum = GenerationModelEnum.GEMINI_2_5_PRO,
    ):
        # Create the ADK-compatible tool
        search_tool = create_adk_search_tool(
            vector_search_service, 
            gemini_service, 
            brand_guideline_repo
        )
        
        system_instruction = (
            "You are the Branding Enforcer Agent for GenMedia Creative Studio. "
            "Your goal is to rewrite user prompts to strictly adhere to the provided brand guidelines.\n"
            "You have access to a tool `search_branding_guidelines` to find relevant rules and reference images.\n"
            "\n"
            "--- EXECUTION STEPS ---\n"
            "1. CHECK the context for `workspace_id` and the user's `original_prompt`.\n"
            "2. CALL `search_branding_guidelines(query=original_prompt, workspace_id=workspace_id)`.\n"
            "3. ANALYZE the tool output deeply:\n"
            "   - **Structured Summaries**: Look for 'Tone of Voice' and 'Visual Style' sections. These are high-priority style directives.\n"
            "   - **Rules Text**: Extract specific adjectives, lighting terms, and composition rules (e.g., 'warm lighting', 'hero product').\n"
            "   - **Reference Images**: The system handles the URIs, but you MUST describe the *style* of these images in your text prompt. If they show a specific mood (e.g. 'cinematic', 'minimalist'), enforce that.\n"

            "4. REWRITE the prompt to be highly detailed and descriptive. EXPAND on the user's intent using the brand's vocabulary.\n"
            "   - **Vocabulary Injection**: If the guidelines mention specific terms (e.g. 'premium', 'authentic', 'approachable'), USE THEM. Match the 'Tone of Voice'.\n"
            "   - **Visual Details**: Define lighting, texture, camera angle, and background based on the 'Visual Style' or specific rules.\n"
            "   - **Constraints**: If negative constraints exist (e.g. 'No gradients'), strictly obey them.\n"
            "   - **Detail Level**: The rewritten prompt should be a rich paragraph involving specific scene descriptions, lighting details, and emotional context.\n"
            "\n"
            "\n"
            "5. OUTPUT the final enhanced prompt text. This text will be used for generation.\n"
            "\n"
            "--- IMPORTANT: REFERENCE IMAGES ---\n"
            "If the tool returns `reference_image_uris`, these are vital visual anchors. "
            "You generally don't need to output the URIs yourself (the system handles them), "
            "but your prompt should description should align with the visual style of these references.\n"
            "\n"
            "Input Context Variables available: {original_prompt}, {workspace_id}\n\n"
            "OUTPUT FORMAT:\n"
            "Return a JSON object with the following structure:\n"
            "{\n"
            "  \"enhanced_prompt\": \"The rewritten prompt string...\",\n"
            "  \"reference_image_uris\": [\"gs://...\", \"gs://...\"],\n"
            "  \"guidelines_used\": \"Summary of guidelines used (e.g. 'Used Visual Style from Guideline A')...\"\n"
            "}\n"
            "Make sure 'enhanced_prompt' contains the final detailed prompt for generation."
        )

        super().__init__(
            name=name,
            model=model,    
            instruction=system_instruction,
            tools=[search_tool],

            # ADK LlmAgent defaults to writing the whole response text to state if output_key is set.
            # If we want structured, we might need to handle it. 
            # Actually, let's keep output_key='last_response' or similar, then parse in AgentService.
            output_key="enforcer_response_json" 
        )
