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

import asyncio
import logging
import httpx
from fastapi import Depends

from src.config.config_service import config_service
from src.common.storage_service import GcsService
from src.galleries.gallery_service import GalleryService
from src.users.user_model import UserModel

logger = logging.getLogger(__name__)


class Web3Service:
    def __init__(
        self,
        gallery_service: GalleryService = Depends(),
        gcs_service: GcsService = Depends(),
    ):
        self.gallery_service = gallery_service
        self.gcs_service = gcs_service
        self.config = config_service

    async def get_nft_metadata(self, item_id: int, current_user: UserModel) -> dict:
        """
        Retrieves a media item by ID and packages its details into standard OpenSea ERC-721 metadata JSON.
        """
        # Retrieve using gallery service which also executes permissions checks
        item = await self.gallery_service.get_media_by_id(
            item_id=item_id, current_user=current_user
        )
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
            attributes.append(
                {"trait_type": "Color & Tone", "value": str(item.color_and_tone)}
            )

        metadata = {
            "name": f"Creative Studio Asset #{item.id}",
            "description": item.prompt
            or "Generative Art created in Google Cloud Creative Studio",
            "image": media_url,
            "external_url": f"https://aetherisx.studio/gallery/{item.id}",
            "attributes": attributes,
            "properties": {
                "original_prompt": item.original_prompt,
                "rewritten_prompt": item.rewritten_prompt,
                "creator": item.user_email,
                "workspace_id": item.workspace_id,
            },
        }

        # If it's video, add animation_url according to ERC-1155/721 standard
        if "video" in str(item.mime_type).lower():
            metadata["animation_url"] = media_url

        return metadata

    async def upload_to_ipfs(self, item_id: int, current_user: UserModel) -> str | None:
        """
        Downloads media asset from GCS, pins it to IPFS via Pinata,
        creates the metadata pointing to the IPFS media URI, pins the metadata to IPFS,
        and returns the final metadata ipfs:// URL.
        """
        if not self.config.PINATA_JWT:
            logger.warning("PINATA_JWT not configured. Skipping IPFS upload.")
            return None

        item = await self.gallery_service.get_media_by_id(
            item_id=item_id, current_user=current_user
        )
        if not item or not item.gcs_uris:
            logger.error(f"Media item {item_id} not found or lacks GCS URI.")
            return None

        # 1. Download the media file bytes from GCS
        try:
            gcs_path = item.gcs_uris[0].replace(
                f"gs://{self.gcs_service.bucket_name}/", ""
            )
            blob = self.gcs_service.bucket.blob(gcs_path)
            media_bytes = await asyncio.to_thread(blob.download_as_bytes)
        except Exception as e:
            logger.error(f"Failed to download media item {item_id} from GCS: {e}")
            return None

        filename = gcs_path.split("/")[-1]
        mime_type = item.mime_type or "image/png"

        # 2. Pin media file bytes to IPFS via Pinata
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {"Authorization": f"Bearer {self.config.PINATA_JWT}"}
                files = {"file": (filename, media_bytes, mime_type)}
                data = {"pinataMetadata": '{"name": "asset-' + str(item_id) + '"}'}

                logger.info(f"Pinning media asset {item_id} to IPFS via Pinata...")
                response = await client.post(
                    "https://api.pinata.cloud/pinning/pinFileToIPFS",
                    headers=headers,
                    files=files,
                    data=data,
                )
                response.raise_for_status()
                res_data = response.json()
                media_ipfs_hash = res_data.get("IpfsHash")
                if not media_ipfs_hash:
                    raise ValueError("Pinata response did not contain IpfsHash.")
                logger.info(f"Media asset pinned successfully. CID: {media_ipfs_hash}")
        except Exception as e:
            logger.error(f"Failed to pin media to IPFS via Pinata: {e}")
            return None

        media_ipfs_url = f"ipfs://{media_ipfs_hash}"

        # 3. Create metadata JSON structure pointing to IPFS media
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
            attributes.append(
                {"trait_type": "Color & Tone", "value": str(item.color_and_tone)}
            )

        metadata = {
            "name": f"Creative Studio Asset #{item.id}",
            "description": item.prompt
            or "Generative Art created in Google Cloud Creative Studio",
            "image": media_ipfs_url,
            "external_url": f"https://aetherisx.studio/gallery/{item.id}",
            "attributes": attributes,
            "properties": {
                "original_prompt": item.original_prompt,
                "rewritten_prompt": item.rewritten_prompt,
                "creator": item.user_email,
                "workspace_id": item.workspace_id,
            },
        }

        if "video" in str(item.mime_type).lower():
            metadata["animation_url"] = media_ipfs_url

        # 4. Pin metadata JSON to IPFS via Pinata
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {
                    "Authorization": f"Bearer {self.config.PINATA_JWT}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "pinataContent": metadata,
                    "pinataMetadata": {"name": f"metadata-asset-{item_id}.json"},
                }

                logger.info(f"Pinning metadata JSON for asset {item_id} to IPFS...")
                response = await client.post(
                    "https://api.pinata.cloud/pinning/pinJSONToIPFS",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                res_data = response.json()
                metadata_ipfs_hash = res_data.get("IpfsHash")
                if not metadata_ipfs_hash:
                    raise ValueError(
                        "Pinata response did not contain metadata IpfsHash."
                    )
                logger.info(f"Metadata pinned successfully. CID: {metadata_ipfs_hash}")
        except Exception as e:
            logger.error(f"Failed to pin metadata JSON to IPFS via Pinata: {e}")
            return None

        return f"ipfs://{metadata_ipfs_hash}"
