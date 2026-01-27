import logging
from typing import List, AsyncGenerator, Any
from google.adk.agents import Agent
from google.adk.tools import AgentTool
from src.common.base_dto import GenerationModelEnum
from src.agents.adk.enforcer import BrandingEnforcerADK
from src.agents.adk.generator import MediaGeneratorADK
from src.agents.adk.validator import ValidatorADK

logger = logging.getLogger(__name__)

def create_creative_director(
    enforcer: BrandingEnforcerADK,
    generation_tool: Any, # Can be BaseTool or AgentTool
    validator: ValidatorADK
) -> Agent:
    """
    Creates the Creative Director agent which orchestrates the generation flow.
    """
    
    instruction = """
    You are the **Creative Director** for a high-end creative studio.
    Your goal is to oversee the creation of on-brand assets by coordinating with your team of specialized tools.
    
    ## YOUR TOOLS:
    1.  **BrandingEnforcer**: Rewrites prompts to be compliant.
    2.  **start_generation** (Tool): Starts the actual media generation. It returns a Job ID.
        - You MUST provide: 
            - `prompt` (The Enhanced Prompt from BrandingEnforcer), 
            - `media_type` (e.g. "IMAGE"), 
            - `workspace_id`, 
            - `user_email`.
            - `number_of_media` (From the config or default 4).
            - `reference_image_uris` (List of strings, if applicable).
    3.  **Validator**: Validates the output using the Job ID.
    
    ## YOUR WORKFLOW:
    1.  **Enforce**: Call `BrandingEnforcer` to get "Enhanced Prompt".
    2.  **Generate**: Call `start_generation` with the Enhanced Prompt, Original Prompt, and other details. 
        - Note: This is a long-running process. You will receive a notification when it is done.
    3.  **Validate**: Once the generation is confirmed and you have the Job ID, call `Validator`.
    4.  **Final Report**: Present the final assets and the validation report.
    """
    
    return Agent(
        name="CreativeDirector",
        model=GenerationModelEnum.GEMINI_2_5_PRO, 
        instruction=instruction,
        tools=[
            AgentTool(agent=enforcer),
            generation_tool, # Direct tool, not wrapped in AgentTool if it's already a Tool
            AgentTool(agent=validator)
        ]
    )
