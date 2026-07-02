// SPDX-License-Identifier: MIT
pragma warning disable
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20;

contract CreativeStudioNFT is ERC721URIStorage, Ownable {
    uint256 private _nextTokenId;
    
    // The LEV token contract address on Base Mainnet
    address public constant LEV_TOKEN = 0xf61771F3C6c2a59C8C99f7f2Fd04684b7182E340;
    
    // Fee in LEV tokens to mint an NFT (e.g., 10 LEV tokens, assuming 18 decimals)
    uint256 public mintFee = 10 * 10**18;

    event NFTMinted(uint256 indexed tokenId, address indexed creator, string tokenURI);
    event MintFeeUpdated(uint256 newFee);

    constructor(address initialOwner) 
        ERC721("Creative Studio NFT", "CSN") 
        Ownable(initialOwner) 
    {
        _nextTokenId = 1;
    }

    /**
     * @dev Mints a new generative AI asset as an NFT.
     * Requires paying the mint fee in LEV tokens to the contract owner.
     */
    function mintCreativeAsset(address creator, string memory tokenURI) public returns (uint256) {
        // Collect LEV token fee from caller (unless caller is the owner)
        if (msg.sender != owner()) {
            require(
                IERC20(LEV_TOKEN).transferFrom(msg.sender, owner(), mintFee),
                "LEV token transfer failed"
            );
        }

        uint256 tokenId = _nextTokenId;
        _nextTokenId++;

        _safeMint(creator, tokenId);
        _setTokenURI(tokenId, tokenURI);

        emit NFTMinted(tokenId, creator, tokenURI);
        return tokenId;
    }

    /**
     * @dev Updates the mint fee in LEV tokens. Only owner.
     */
    function setMintFee(uint256 newFee) external onlyOwner {
        mintFee = newFee;
        emit MintFeeUpdated(newFee);
    }
}
