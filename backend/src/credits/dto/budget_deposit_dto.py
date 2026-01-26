# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from typing import Optional
from pydantic import BaseModel, Field
from decimal import Decimal

class CreateBudgetDepositDto(BaseModel):
    amount_usd: Decimal = Field(..., gt=0, description="The amount in USD to deposit.")
    notes: Optional[str] = Field(None, description="Optional notes for this deposit.")

class BudgetDepositDto(BaseModel):
    id: int
    amount_usd: Decimal
    notes: Optional[str]
    timestamp: datetime.datetime

    class Config:
        orm_mode = True
