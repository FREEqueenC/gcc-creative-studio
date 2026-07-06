# Copyright 2026 FREEqueenC
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from typing import Dict, Any
from web3 import Web3


class BaseWeb3Provider(ABC):
    @abstractmethod
    async def prepare_mint(self, item_id: int, metadata_url: str) -> Dict[str, Any]:
        """
        Prepares the parameters required for minting an NFT on this chain.
        """
        pass


class EvmWeb3Provider(BaseWeb3Provider):
    def __init__(self, contract_address: str, mint_fee: str):
        if not Web3.is_address(contract_address):
            raise ValueError(f"Invalid EVM contract address format: {contract_address}")
        self.contract_address = Web3.to_checksum_address(contract_address)
        self.mint_fee = mint_fee

    async def prepare_mint(self, item_id: int, metadata_url: str) -> Dict[str, Any]:
        # Under Ethereum/Base, the client interacts with the smart contract directly.
        # We package the target parameters for front-end Web3 provider execution.
        return {
            "contract_address": self.contract_address,
            "metadata_url": metadata_url,
            "item_id": item_id,
            "mint_fee": self.mint_fee,
            "chain_type": "evm",
        }


class FlowWeb3Provider(BaseWeb3Provider):
    def __init__(self, contract_address: str, mint_fee: str):
        # Validate Flow Cadence contract address format (e.g. A.address.ContractName or address)
        if not contract_address:
            raise ValueError("Flow contract address cannot be empty")
        self.contract_address = contract_address
        self.mint_fee = mint_fee

    async def prepare_mint(self, item_id: int, metadata_url: str) -> Dict[str, Any]:
        # Under Flow Cadence, we return the transaction script and arguments.
        # This allows the frontend FCL (Flow Client Library) to execute it.
        cadence_mint_script = """
        import CreativeStudioNFT from 0xCreativeStudioNFT

        transaction(recipient: Address, url: String) {
            let minterRef: &CreativeStudioNFT.Minter

            prepare(signer: AuthAccount) {
                self.minterRef = signer.borrow<&CreativeStudioNFT.Minter>(from: /storage/CreativeStudioNFTMinter)
                    ?? panic("Could not borrow minter reference")
            }

            execute {
                let nft <- self.minterRef.mintNFT(creator: recipient, metadata: {"url": url})
                let receiverRef = getAccount(recipient)
                    .getCapability(/public/CreativeStudioNFTCollection)
                    .borrow<&CreativeStudioNFT.Collection>()
                    ?? panic("Could not borrow receiver collection reference")
                
                receiverRef.deposit(token: <-nft)
            }
        }
        """
        return {
            "contract_address": self.contract_address,
            "metadata_url": metadata_url,
            "item_id": item_id,
            "mint_fee": self.mint_fee,
            "chain_type": "flow",
            "cadence_script": cadence_mint_script.strip(),
        }
