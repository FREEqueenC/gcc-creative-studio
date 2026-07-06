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

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.auth.auth_guard import RoleChecker, get_current_user
from src.users.user_model import UserModel, UserRoleEnum
from src.web3.web3_service import Web3Service
from src.web3.providers import EvmWeb3Provider, FlowWeb3Provider

router = APIRouter(
    prefix="/api/web3",
    tags=["Creative Studio Web3 & NFT Services"],
    responses={404: {"description": "Not found"}},
)


class PrepareMintRequest(BaseModel):
    item_id: int
    chain: str  # "base" or "flow"


class PrepareMintResponse(BaseModel):
    contract_address: str
    metadata_url: str
    item_id: int
    mint_fee: str
    chain_type: str
    cadence_script: Optional[str] = None


# Standard User role check for the prepare-mint endpoint
user_only = Depends(RoleChecker(allowed_roles=[UserRoleEnum.USER, UserRoleEnum.ADMIN]))


@router.post(
    "/prepare-mint", response_model=PrepareMintResponse, dependencies=[user_only]
)
async def prepare_mint(
    request: PrepareMintRequest,
    current_user: UserModel = Depends(get_current_user),
    service: Web3Service = Depends(),
):
    """
    Prepares the metadata and parameters for minting a generated creative asset as an NFT.
    Returns the contract address and the metadata URL.
    """
    metadata = await service.get_nft_metadata(
        item_id=request.item_id, current_user=current_user
    )
    if not metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media item not found or user lacks permission to access it.",
        )

    # Instantiate the correct blockchain provider
    try:
        if request.chain.lower() == "base":
            # Target contract on Base Mainnet
            provider = EvmWeb3Provider(
                contract_address="0x81631e082767e0F545386420cCB1128b98C70F60",
                mint_fee="10 LEV",
            )
        elif request.chain.lower() == "flow":
            # Target contract on Flow Mainnet/Testnet
            provider = FlowWeb3Provider(
                contract_address="A.0x81631e082767e0F545386420cCB1128b98C70F60.CreativeStudioNFT",
                mint_fee="0 FLOW",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid chain. Supported values are 'base' or 'flow'.",
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Attempt to pin media and metadata to IPFS/Pinata if configured, else fall back to local dynamic hosting.
    ipfs_url = await service.upload_to_ipfs(
        item_id=request.item_id, current_user=current_user
    )
    metadata_url = ipfs_url if ipfs_url else f"/api/web3/metadata/{request.item_id}"

    # Generate provider mint parameters
    mint_params = await provider.prepare_mint(
        item_id=request.item_id, metadata_url=metadata_url
    )

    return PrepareMintResponse(
        contract_address=mint_params["contract_address"],
        metadata_url=mint_params["metadata_url"],
        item_id=mint_params["item_id"],
        mint_fee=mint_params["mint_fee"],
        chain_type=mint_params["chain_type"],
        cadence_script=mint_params.get("cadence_script"),
    )


# GET metadata endpoint is PUBLIC (no auth required) so NFT standard indexing works.
@router.get("/metadata/{item_id}")
async def get_nft_metadata_public(
    item_id: int,
    service: Web3Service = Depends(),
):
    """
    Public metadata endpoint for external NFT platforms and contracts to resolve token metadata.
    """
    # For public indexers, we bypass current user credentials but use a read-only admin context
    # to retrieve the requested record details securely.
    indexer_mock_user = UserModel(
        email="indexer@creative-studio.internal", roles=[UserRoleEnum.ADMIN]
    )
    metadata = await service.get_nft_metadata(
        item_id=item_id, current_user=indexer_mock_user
    )
    if not metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Metadata not found."
        )
    return metadata
