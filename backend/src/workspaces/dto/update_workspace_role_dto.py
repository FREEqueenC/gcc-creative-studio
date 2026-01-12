from pydantic import BaseModel
from src.workspaces.schema.workspace_model import WorkspaceRoleEnum

class UpdateWorkspaceRoleDto(BaseModel):
    role: WorkspaceRoleEnum
