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

from typing import Optional
from pydantic import Field
from pydantic.alias_generators import to_camel
from src.common.base_dto import BaseDto

class UpdateOrganizationDto(BaseDto):
    """
    DTO for updating an organization.
    CRITICAL: 'domain' is NOT included as it cannot be changed.
    """
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    logo: Optional[str] = Field(None, description="GCS URI of the logo (e.g., gs://bucket/path/image.png)")
