from pydantic import BaseModel
from src.organizations.organization_model import OrganizationRoleEnum

class UpdateOrganizationRoleDto(BaseModel):
    role: OrganizationRoleEnum
