import logging
from typing import Dict, Any, List

# ADK Imports
# Note: Assuming google.adk is installed. If not, this might fail at runtime until dependency is resolved.
from google.adk.tools import FunctionTool

# Backend Imports
from src.tools.vector_search_tool import create_search_branding_guidelines_tool
from src.common.vector_search_service import VectorSearchService
from src.multimodal.gemini_service import GeminiService
from src.brand_guidelines.repository.brand_guideline_repository import BrandGuidelineRepository

logger = logging.getLogger(__name__)

def create_adk_search_tool(
    vector_search_service: VectorSearchService, 
    gemini_service: GeminiService, 
    brand_guideline_repo: BrandGuidelineRepository
) -> FunctionTool:
    """
    Creates an ADK-compatible FunctionTool for searching branding guidelines.
    """
    
    # 1. Get the underlying async function from the existing factory
    # This returns: async def search_branding_guidelines(query: str, workspace_id: str = "Global")
    native_tool_fn = create_search_branding_guidelines_tool(
        vector_search_service, 
        gemini_service, 
        brand_guideline_repo
    )

    # 2. Define the schema if necessary, OR let ADK infer it from the function signature.
    # The existing function has type hints, so ADK should be able to infer.
    # We wrap it directly.
    
    # NOTE: ADK FunctionTool expects a callable.
    # The tool will extract name and description from the function's __name__ and __doc__.
    tool = FunctionTool(
        func=native_tool_fn
    )
    
    return tool
