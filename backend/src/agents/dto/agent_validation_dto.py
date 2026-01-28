from typing import List, Optional, Any
from pydantic import BaseModel, Field

class AgentValidationResult(BaseModel):
    """
    Standardized result object for ADK Validator agents.
    Used to pass structured data from Agent -> Backend/Frontend.
    """
    is_compliant: bool = Field(..., description="Whether the asset adheres to all guidelines.")
    score: int = Field(..., ge=0, le=100, description="Compliance score from 0-100.")
    reasoning: str = Field(..., description="Detailed explanation of the validation result.")
    issues: List[str] = Field(default_factory=list, description="List of specific compliance issues found.")
    
    # Optional raw data if needed for debugging or legacy compat
    raw_response: Optional[Any] = Field(None, description="Raw JSON response from the LLM if applicable.")
