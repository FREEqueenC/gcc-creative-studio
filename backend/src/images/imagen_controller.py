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

from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, Request
from fastapi import status as Status

from src.auth.auth_guard import RoleChecker, get_current_user
from src.galleries.dto.gallery_response_dto import MediaItemResponse
from src.images.dto.create_imagen_dto import CreateImagenDto
from src.images.dto.upscale_imagen_dto import UpscaleImagenDto
from src.images.dto.vto_dto import VtoDto
from src.images.imagen_service import ImagenService
from src.images.schema.imagen_result_model import ImageGenerationResult
from src.users.user_model import UserModel, UserRoleEnum
from src.workspaces.workspace_auth_guard import WorkspaceAuth
from src.source_assets.schema.source_asset_model import (
    AssetScopeEnum,
    AssetTypeEnum,
)
from src.common.base_dto import AspectRatioEnum
from src.common.base_dto import (
    AspectRatioEnum,
)

# Define role checkers for convenience
user_only = Depends(
    RoleChecker(allowed_roles=[UserRoleEnum.USER, UserRoleEnum.ADMIN])
)

router = APIRouter(
    prefix="/api/images",
    tags=["Google Imagen APIs"],
    responses={404: {"description": "Not found"}},
    dependencies=[user_only],
)


@router.post("/generate-images")
async def generate_images(
    image_request: CreateImagenDto,
    request: Request,
    service: ImagenService = Depends(),
    current_user: UserModel = Depends(get_current_user),
    workspace_auth: WorkspaceAuth = Depends(),
) -> MediaItemResponse | None:
    try:
        # Use our centralized dependency to authorize the user for the workspace
        # before proceeding with the expensive generation job.
        await workspace_auth.authorize(
            workspace_id=image_request.workspace_id, user=current_user
        )

        # Get the executor from the app state
        executor = request.app.state.executor

        return await service.start_image_generation_job(
            request_dto=image_request, user=current_user, executor=executor
        )
    except HTTPException as http_exception:
        raise http_exception
    except ValueError as value_error:
        raise HTTPException(
            status_code=Status.HTTP_400_BAD_REQUEST,
            detail=str(value_error),
        )
    except Exception as e:
        raise HTTPException(
            status_code=Status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/generate-images-for-vto")
async def generate_images_vto(
    image_request: VtoDto,
    request: Request,
    service: ImagenService = Depends(),
    current_user: UserModel = Depends(get_current_user),
    workspace_auth: WorkspaceAuth = Depends(),
) -> MediaItemResponse | None:
    """Start an async VTO generation job. Returns immediately with a placeholder."""
    try:
        await workspace_auth.authorize(
            workspace_id=image_request.workspace_id, user=current_user
        )

        # Get the process pool from the application state
        executor = request.app.state.executor

        placeholder_item = await service.start_vto_generation_job(
            request_dto=image_request,
            user=current_user,
            executor=executor,
        )
        return placeholder_item
    except HTTPException as http_exception:
        raise http_exception
    except ValueError as value_error:
        raise HTTPException(
            status_code=Status.HTTP_400_BAD_REQUEST,
            detail=str(value_error),
        )
    except Exception as e:
        raise HTTPException(
            status_code=Status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    

@router.post("/upload-upscale", response_model=MediaItemResponse)
async def upload_upscale(
    request: Request,
    file: Optional[UploadFile] = File(None),
    scope: Optional[AssetScopeEnum] = Form(None),
    mime_type: Optional[str] = Form(None, alias="mimeType"),
    source_asset_id: Optional[int] = Form(None, alias="id"),
    media_item_id: Optional[int] = Form(None, alias="mediaItemId"),
    gcs_uri: Optional[str] = Form(None, alias="gcsUri"),
    original_filename: Optional[str] = Form(None, alias="originalFilename"),
    workspace_id: int = Form(alias="workspaceId"),
    aspectRatio: Optional[AspectRatioEnum] = Form(None),
    upscale_factor: Optional[str] = Form(None, alias="upscaleFactor"),
    file_hash: Optional[str] = Form(None, alias="fileHash"),
    assetType: Optional[AssetTypeEnum] = Form(None),
    enhance_input_image: Optional[bool] = Form(None, alias="enhance_input_image"),
    image_preservation_factor: Optional[float] = Form(None, alias="image_preservation_factor"),
    current_user: UserModel = Depends(get_current_user),
    service: ImagenService = Depends(),
    workspace_auth: WorkspaceAuth = Depends(),
) -> MediaItemResponse:
    
    file_bytes = None
    filename = None
    if file:
        file_bytes = await file.read()
        filename = file.filename
    await workspace_auth.authorize(workspace_id=workspace_id, user=current_user)
    
    executor = request.app.state.executor

    return await service.start_upload_upscale_job(
        user=current_user,
        executor=executor,
        workspace_id=workspace_id,
        source_asset_id=source_asset_id,
        media_item_id_existing=media_item_id,
        upscale_factor=upscale_factor,
        aspect_ratio=aspectRatio,
        asset_type=assetType,
        gcs_uri=gcs_uri,
        file_bytes=file_bytes, 
        filename=filename,
        original_filename = original_filename,
        file_hash=file_hash,
        scope=scope,
        mime_type=mime_type,
        enhance_input_image=enhance_input_image,
        image_preservation_factor=image_preservation_factor,
    )
    

@router.post("/upscale-image")
async def upscale_image(
    image_request: UpscaleImagenDto,
    service: ImagenService = Depends(),
) -> ImageGenerationResult | None:
    try:
        return await service.upscale_image(request_dto=image_request)
    except HTTPException as http_exception:
        raise http_exception
    except ValueError as value_error:
        raise HTTPException(
            status_code=Status.HTTP_400_BAD_REQUEST,
            detail=str(value_error),
        )
    except Exception as e:
        raise HTTPException(
            status_code=Status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


