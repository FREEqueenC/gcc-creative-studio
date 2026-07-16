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

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.web3.web3_service import Web3Service

@pytest.mark.asyncio
async def test_get_nft_metadata_success(mock_user):
    mock_item = MagicMock()
    mock_item.id = 42
    mock_item.model = "imagen-3.0"
    mock_item.aspect_ratio = "1:1"
    mock_item.mime_type = "image/png"
    mock_item.style = "cyberpunk"
    mock_item.seed = 12345
    mock_item.lighting = "neon"
    mock_item.color_and_tone = "vibrant"
    mock_item.prompt = "A cyberpunk city"
    mock_item.original_prompt = "A cyberpunk city prompt"
    mock_item.rewritten_prompt = "A cyberpunk city rewritten"
    mock_item.user_email = "user@example.com"
    mock_item.workspace_id = 1
    mock_item.presigned_urls = ["http://example.com/presigned.png"]
    mock_item.gcs_uris = ["gs://my-bucket/image.png"]

    gallery_service = AsyncMock()
    gallery_service.get_media_by_id.return_value = mock_item

    gcs_service = MagicMock()
    service = Web3Service(gallery_service=gallery_service, gcs_service=gcs_service)

    res = await service.get_nft_metadata(item_id=42, current_user=mock_user)

    assert res["name"] == "Creative Studio Asset #42"
    assert res["image"] == "http://example.com/presigned.png"
    assert res["external_url"] == "https://aetherisx.studio/gallery/42"
    assert any(attr["value"] == "cyberpunk" for attr in res["attributes"])

@pytest.mark.asyncio
async def test_upload_to_ipfs_no_jwt(mock_user):
    gallery_service = AsyncMock()
    gcs_service = MagicMock()
    service = Web3Service(gallery_service=gallery_service, gcs_service=gcs_service)

    with patch.object(service.config, "PINATA_JWT", ""):
        res = await service.upload_to_ipfs(item_id=42, current_user=mock_user)
        assert res is None
