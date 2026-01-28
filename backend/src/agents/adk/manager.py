import logging
from typing import List, AsyncGenerator, Any
from google.adk.agents import Agent
from google.adk.tools import AgentTool
from src.common.base_dto import GenerationModelEnum
from src.agents.adk.enforcer import BrandingEnforcerADK
from src.agents.adk.generator import MediaGeneratorADK
from src.agents.adk.validator import ValidatorADK

logger = logging.getLogger(__name__)

# New ADK Agents
from google.adk.agents import SequentialAgent, LlmAgent
from src.agents.adk.enforcer import BrandingEnforcerADK
from src.agents.adk.generator import MediaGeneratorADK
from src.agents.adk.validator import ValidatorADK
from src.agents.adk.poller import JobPollerADK

def create_media_pipeline(
    enforcer: BrandingEnforcerADK,
    generator_agent: MediaGeneratorADK, 
    poller: JobPollerADK,
    validator: ValidatorADK
) -> SequentialAgent:
    """
    Creates the Sequential Pipeline: Enforcer -> Generator -> Poller -> Validator.
    Using SequentialAgent ensures deterministic execution order.
    """
    
    return SequentialAgent(
        name="MediaGenerationPipeline",
        sub_agents=[
            enforcer,
            generator_agent,
            poller,
            validator
        ],
        description="Robust pipeline: Enforce -> Generate -> Poll (Wait) -> Validate."
    )
