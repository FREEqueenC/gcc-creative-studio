from pydantic import BaseModel

class PermissionCheckDto(BaseModel):
    object_type: str
    object_id: str
    relation: str
