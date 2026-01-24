from enum import StrEnum

class WorkspacePermissionEnum(StrEnum):
    # Base Roles
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    OWNER = "owner"

    # Member Management
    CAN_INVITE_WS_MEMBERS = "can_invite_ws_members"
    CAN_ADD_WS_MEMBERS = "can_add_ws_members"
    CAN_REMOVE_WS_MEMBERS = "can_remove_ws_members"
    CAN_ASSIGN_WS_ROLES = "can_assign_ws_roles"

    # Workflows
    CAN_VIEW_WS_WORKFLOWS = "can_view_ws_workflows"
    CAN_EXECUTE_WS_WORKFLOWS = "can_execute_ws_workflows"
    CAN_EDIT_WS_WORKFLOWS = "can_edit_ws_workflows"

    # Brand Guidelines
    CAN_VIEW_WS_BRAND_GUIDELINES = "can_view_ws_brand_guidelines"
    CAN_EDIT_WS_BRAND_GUIDELINES = "can_edit_ws_brand_guidelines"

    # GenAI Features
    CAN_GENERATE_IMAGES = "can_generate_images"
    CAN_VIEW_IMAGES = "can_view_images"
    CAN_GENERATE_VIDEOS = "can_generate_videos"
    CAN_VIEW_VIDEOS = "can_view_videos"
    CAN_GENERATE_AUDIO = "can_generate_audio"
    CAN_VIEW_AUDIO = "can_view_audio"
    CAN_GENERATE_VTO = "can_generate_vto"
    CAN_VIEW_VTO = "can_view_vto"

class OrganizationPermissionEnum(StrEnum):
    # Base Roles
    ADMIN = "admin"
    MEMBER = "member"
    OWNER = "owner"
    
    # Organization Management
    CAN_EDIT_ORGANIZATION = "can_edit_organization"
    
    # Member Management
    CAN_INVITE_ORG_MEMBERS = "can_invite_org_members"
    CAN_ADD_ORG_MEMBERS = "can_add_org_members"
    CAN_REMOVE_ORG_MEMBERS = "can_remove_org_members"
    CAN_ASSIGN_ORG_ROLES = "can_assign_org_roles"

    # Brand Guidelines
    CAN_EDIT_ORG_BRAND_GUIDELINES = "can_edit_org_brand_guidelines"
    CAN_VIEW_ORG_BRAND_GUIDELINES = "can_view_org_brand_guidelines"

    # Admin Panel
    CAN_ACCESS_ADMIN_PANEL = "can_access_admin_panel"
    CAN_VIEW_ALL_ORG_WORKSPACES = "can_view_all_org_workspaces"
