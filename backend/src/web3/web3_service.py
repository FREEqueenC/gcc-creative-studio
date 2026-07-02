# Copyright 2026 Google LLC
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

from fastapi import Depends
from src.galleries.gallery_service import GalleryService
from src.users.user_model import UserModel

class Web3Service:
    def __init__(self, gallery_service: GalleryService = Depends()):
        self.gallery_service = gallery_service

    async def get_nft_metadata(self, item_id: int, current_user: UserModel) -> dict:
        """
        Retrieves a media item by ID and packages its details into standard OpenSea ERC-721 metadata JSON.
        """
        # Retrieve using gallery service which also executes permissions checks
        item = await self.gallery_service.get_media_by_id(item_id=item_id, current_user=current_user)
        if not item:
            return {}

        # Get presigned URL or direct GCS URL
        media_url = ""
        if item.presigned_urls:
            media_url = item.presigned_urls[0]
        elif item.gcs_uris:
            media_url = item.gcs_uris[0]

        attributes = [
            {"trait_type": "AI Model", "value": str(item.model)},
            {"trait_type": "Aspect Ratio", "value": str(item.aspect_ratio)},
            {"trait_type": "Mime Type", "value": str(item.mime_type)},
        ]
        
        if item.style:
            attributes.append({"trait_type": "Style", "value": str(item.style)})
        if item.seed is not None:
            attributes.append({"trait_type": "Seed", "value": int(item.seed)})
        if item.lighting:
            attributes.append({"trait_type": "Lighting", "value": str(item.lighting)})
        if item.color_and_tone:
            attributes.append({"trait_type": "Color & Tone", "value": str(item.color_and_tone)})

        metadata = {
            "name": f"Creative Studio Asset #{item.id}",
            "description": item.prompt or "Generative Art created in Google Cloud Creative Studio",
            "image": media_url,
            "external_url": f"https://freequeenc.github.io/gcc-creative-studio/gallery/{item.id}",
            "attributes": attributes,
            "properties": {
                "original_prompt": item.original_prompt,
                "rewritten_prompt": item.rewritten_prompt,
                "creator": item.user_email,
                "workspace_id": item.workspace_id,
            }
        }
        
        # If it's video, add animation_url according to ERC-1155/721 standard
        if "video" in str(item.mime_type).lower():
            metadata["animation_url"] = media_url

        return metadata
