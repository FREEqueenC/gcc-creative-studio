import logging
import os
from openfga_sdk import OpenFgaClient
from openfga_sdk.models.create_store_request import CreateStoreRequest
from openfga_sdk.models.write_authorization_model_request import WriteAuthorizationModelRequest

logger = logging.getLogger(__name__)

STORE_NAME = "Creative Studio"

async def setup_fga(client: OpenFgaClient):
    """
    Ensures the OpenFGA store exists and has the correct authorization model.
    Updates the client with the store ID.
    """
    logger.info("Setting up OpenFGA...")
    
    # 1. Check/Create Store
    store_id = os.getenv("OPENFGA_STORE_ID")
    
    # Basic ULID validation (26 alphanumeric characters)
    # If the user accidentally set the Name as the ID, we should ignore it and find by name.
    if store_id and (len(store_id) != 26 or not store_id.isalnum()):
        logger.warning(f"Invalid OPENFGA_STORE_ID format: '{store_id}'. Expected 26-char ULID. Ignoring and searching by name.")
        store_id = None

    if not store_id:
        try:
            # List stores to find existing one
            logger.info("OPENFGA_STORE_ID not set or invalid. Attempting to find or create store...")
            response = await client.list_stores()
            store = next((s for s in response.stores if s.name == STORE_NAME), None)
            
            if store:
                store_id = store.id
                logger.info(f"Found existing OpenFGA store: {store.name} ({store_id})")
            else:
                logger.info(f"Creating new OpenFGA store: {STORE_NAME}...")
                response = await client.create_store(CreateStoreRequest(name=STORE_NAME))
                store_id = response.id
                logger.info(f"Created new OpenFGA store: {store_id}")
        except Exception as e:
            logger.error(f"Failed to list/create OpenFGA store: {e}")
            # We might want to re-raise or handle gracefully, but for now let's re-raise
            # so the backend knows something is wrong.
            raise e
    else:
        logger.info(f"Using configured OPENFGA_STORE_ID: {store_id}")

    # 2. Update Client with Store ID
    client.set_store_id(store_id)

    # 3. Write Authorization Model
    # We always try to write the model to ensure it's up to date.
    # OpenFGA handles deduplication (if model is same, it might return existing ID or new ID).
    
    type_definitions = [
        {"type": "user"},
        {
            "type": "platform",
            "relations": {
                "super_admin": {"this": {}}
            },
            "metadata": {
                "relations": {
                    "super_admin": {"directly_related_user_types": [{"type": "user"}]}
                }
            }
        },
        {
            "type": "organization",
            "relations": {
                "platform": {"this": {}},
                "admin": {
                    "union": {
                        "child": [
                            {"this": {}},
                            {"tupleToUserset": {"computedUserset": {"object": "", "relation": "super_admin"}, "tupleset": {"object": "", "relation": "platform"}}}
                        ]
                    }
                },
                "member": {
                    "union": {
                        "child": [
                            {"this": {}},
                            {"computedUserset": {"object": "", "relation": "admin"}}
                        ]
                    }
                },
                
                # --- MEMBER MANAGEMENT (Granular) ---
                "can_invite_org_members": {"computedUserset": {"object": "", "relation": "admin"}},
                "can_add_org_members": {"computedUserset": {"object": "", "relation": "admin"}},
                "can_remove_org_members": {"computedUserset": {"object": "", "relation": "admin"}},
                "can_assign_org_roles": {"computedUserset": {"object": "", "relation": "admin"}},
                                
                # --- ORG GUIDELINES (Split) ---
                # Edit: Strictly Admins
                "can_edit_org_brand_guidelines": {"computedUserset": {"object": "", "relation": "admin"}},
                # View: All Members (Everyone in the org needs to see the logo/fonts)
                "can_view_org_brand_guidelines": {"computedUserset": {"object": "", "relation": "member"}},
                
                "can_access_admin_panel": {"computedUserset": {"object": "", "relation": "admin"}},
                "can_view_all_org_workspaces": {"computedUserset": {"object": "", "relation": "admin"}}
            },
            "metadata": {
                "relations": {
                    "platform": {"directly_related_user_types": [{"type": "platform"}]},
                    "admin": {"directly_related_user_types": [{"type": "user"}]},
                    "member": {"directly_related_user_types": [{"type": "user"}]},
                    
                    "can_invite_org_members": {"directly_related_user_types": []},
                    "can_add_org_members": {"directly_related_user_types": []},
                    "can_remove_org_members": {"directly_related_user_types": []},
                    "can_assign_org_roles": {"directly_related_user_types": []},
                    
                    "can_edit_org_brand_guidelines": {"directly_related_user_types": []},
                    "can_view_org_brand_guidelines": {"directly_related_user_types": []},
                                        
                    "can_access_admin_panel": {"directly_related_user_types": []},
                    "can_view_all_org_workspaces": {"directly_related_user_types": []}
                }
            }
        },
        {
            "type": "workspace",
            "relations": {
                "parent": {"this": {}},
                
                # --- Base Roles (Synced from DB) ---
                "admin": {"union": {"child": [{"this": {}}, {"tupleToUserset": {"computedUserset": {"object": "", "relation": "admin"}, "tupleset": {"object": "", "relation": "parent"}}}]}},
                "editor": {"union": {"child": [{"this": {}}, {"computedUserset": {"object": "", "relation": "admin"}}]}},
                "viewer": {"union": {"child": [{"this": {}}, {"computedUserset": {"object": "", "relation": "editor"}}]}},
                
                # --- WORKSPACE MEMBER MANAGEMENT (Explicit) ---
                "can_invite_ws_members": {"computedUserset": {"object": "", "relation": "admin"}},
                "can_add_ws_members": {"computedUserset": {"object": "", "relation": "admin"}},
                "can_remove_ws_members": {"computedUserset": {"object": "", "relation": "admin"}},
                "can_assign_ws_roles": {"computedUserset": {"object": "", "relation": "admin"}},
                
                # --- Feature Add-Ons (Keys) ---
                "workflow_add_on": {"this": {}},
                "brand_guidelines_add_on": {"this": {}},

                # --- A. Workflows Module (Granular + Gated) ---
                # VIEW: Admin OR (Viewer + AddOn)
                "can_view_ws_workflows": {
                    "union": {
                        "child": [
                            {"computedUserset": {"object": "", "relation": "admin"}},
                            {"intersection": {
                                "child": [
                                    {"computedUserset": {"object": "", "relation": "viewer"}},
                                    {"computedUserset": {"object": "", "relation": "workflow_add_on"}}
                                ]
                            }}
                        ]
                    }
                },
                
                # EXECUTE: Admin OR (Editor + AddOn)
                "can_execute_ws_workflows": {
                    "union": {
                        "child": [
                            {"computedUserset": {"object": "", "relation": "admin"}},
                            {"intersection": {
                                "child": [
                                    {"computedUserset": {"object": "", "relation": "editor"}},
                                    {"computedUserset": {"object": "", "relation": "workflow_add_on"}}
                                ]
                            }}
                        ]
                    }
                },
                
                # EDIT: Admin OR (Editor + AddOn)
                "can_edit_ws_workflows": {
                    "union": {
                        "child": [
                            {"computedUserset": {"object": "", "relation": "admin"}},
                            {"intersection": {
                                "child": [
                                    {"computedUserset": {"object": "", "relation": "editor"}},
                                    {"computedUserset": {"object": "", "relation": "workflow_add_on"}}
                                ]
                            }}
                        ]
                    }
                },


                # --- B. Brand Guidelines Module (Granular + Gated) ---
                
                # VIEW: All Workspace Members (Admin, Editor, Viewer)
                # Logic: Everyone in the workspace should be able to see the brand guidelines
                "can_view_ws_brand_guidelines": {"computedUserset": {"object": "", "relation": "viewer"}},

                # EDIT: Admin OR (Editor + Add-On)
                # Logic: Only Editors with the add-on can upload new logos/colors.
                "can_edit_ws_brand_guidelines": {
                    "union": {
                        "child": [
                            {"computedUserset": {"object": "", "relation": "admin"}},
                            {"intersection": {
                                "child": [
                                    {"computedUserset": {"object": "", "relation": "editor"}},
                                    {"computedUserset": {"object": "", "relation": "brand_guidelines_add_on"}}
                                ]
                            }}
                        ]
                    }
                },

                # --- C. Standard Features (GenAI) ---
                "can_generate_images": {"computedUserset": {"object": "", "relation": "editor"}},
                "can_view_images": {"computedUserset": {"object": "", "relation": "viewer"}},
                "can_generate_videos": {"computedUserset": {"object": "", "relation": "editor"}},
                "can_view_videos": {"computedUserset": {"object": "", "relation": "viewer"}},
                "can_generate_audio": {"computedUserset": {"object": "", "relation": "editor"}},
                "can_view_audio": {"computedUserset": {"object": "", "relation": "viewer"}},
                "can_generate_vto": {"computedUserset": {"object": "", "relation": "editor"}},
                "can_view_vto": {"computedUserset": {"object": "", "relation": "viewer"}}
            },
            "metadata": {
                "relations": {
                    "parent": {"directly_related_user_types": [{"type": "organization"}]},
                    
                    # Roles
                    "admin": {"directly_related_user_types": [{"type": "user"}]},
                    "editor": {"directly_related_user_types": [{"type": "user"}]},
                    "viewer": {"directly_related_user_types": [{"type": "user"}, {"type": "user", "wildcard": {}}]},
                    
                    # Workspace Member Management
                    "can_invite_ws_members": {"directly_related_user_types": []},
                    "can_add_ws_members": {"directly_related_user_types": []},
                    "can_remove_ws_members": {"directly_related_user_types": []},
                    "can_assign_ws_roles": {"directly_related_user_types": []},
                    
                    # Add-Ons
                    "workflow_add_on": {"directly_related_user_types": [{"type": "user"}]},
                    "brand_guidelines_add_on": {"directly_related_user_types": [{"type": "user"}]},
                    
                    # Workflow Permissions
                    "can_view_ws_workflows": {"directly_related_user_types": []},
                    "can_execute_ws_workflows": {"directly_related_user_types": []},
                    "can_edit_ws_workflows": {"directly_related_user_types": []},
                    
                    # Brand Guidelines Permissions
                    "can_view_ws_brand_guidelines": {"directly_related_user_types": []},
                    "can_edit_ws_brand_guidelines": {"directly_related_user_types": []},
                    
                    # GenAI Permissions
                    "can_generate_images": {"directly_related_user_types": []},
                    "can_view_images": {"directly_related_user_types": []},
                    "can_generate_videos": {"directly_related_user_types": []},
                    "can_view_videos": {"directly_related_user_types": []},
                    "can_generate_audio": {"directly_related_user_types": []},
                    "can_view_audio": {"directly_related_user_types": []},
                    "can_generate_vto": {"directly_related_user_types": []},
                    "can_view_vto": {"directly_related_user_types": []}
                }
            }
        }
    ]

    try:
        logger.info("Writing OpenFGA authorization model...")
        request = WriteAuthorizationModelRequest(
            schema_version="1.1",
            type_definitions=type_definitions
        )
        response = await client.write_authorization_model(request)
        model_id = response.authorization_model_id
        logger.info(f"OpenFGA authorization model written: {model_id}")
    except Exception as e:
        logger.error(f"Failed to write OpenFGA authorization model: {e}")
        # This is critical, so we raise
        raise e

    # Log helpful info for the user
    logger.info("-" * 60)
    logger.info(f"✅ OpenFGA Setup Complete!")
    logger.info(f"Store ID: {store_id}")
    logger.info(f"Model ID: {model_id}")
    logger.info("-" * 60)
    logger.info("🚀 Access the Playground here:")
    logger.info(f"http://localhost:3000/playground?store_id={store_id}")
    logger.info("-" * 60)
    logger.info("ℹ️  OpenFGA is running on port 8080 (Default).")
    logger.info("    The Backend is accessible at http://localhost:9000")
    logger.info("    Note: If you see CORS errors in the OpenFGA Playground, try disabling")
    logger.info("    'Local Network Access Check' in chrome://flags/#local-network-access-check")
    logger.info("-" * 60)

    return store_id
