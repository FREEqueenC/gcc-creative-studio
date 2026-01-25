from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime

class AssignCreditsDto(BaseModel):
    target_user_id: Optional[int] = None
    target_org_id: Optional[int] = None
    amount: float = Field(..., gt=0, description="Amount of credits to assign")
    custom_expiration_date: Optional[datetime] = None
    
    # Validator to ensure at least one target is set
    def model_post_init(self, __context):
        if not self.target_user_id and not self.target_org_id:
            raise ValueError("Either target_user_id or target_org_id must be provided")
