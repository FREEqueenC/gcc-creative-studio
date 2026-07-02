# Creative Studio NFT - Cadence Smart Contract Design

This document details the four-stage methodology followed to build the Cadence smart contract for tokenizing Creative Studio multimedia assets.

---

## Stage 1: Idea (Asset structure and capability security)
The goal is to represent high-fidelity generative AI media (images, videos, audio) as unique on-chain digital assets on the Flow Blockchain.
* **Asset Payload**: Each NFT represents a generated creative asset. It must capture the creative provenance: the prompt used, the model (e.g., Imagen 3, Veo), generation settings, creator's identity, and the media URI (stored in Google Cloud Storage or IPFS).
* **Capability Security**: Cadence uses capability-based security. Only the owner of the resource should have the power to withdraw it. The public should only be able to view IDs, deposit NFTs, or query metadata.

---

## Stage 2: Visualization (Resource ownership and collection mapping)
In Cadence, resources are first-class citizens. They cannot be copied or implicitly discarded; they must be moved explicitly via the `<-` operator.
* **NFT Resource (`@NFT`)**: A resource holding the unique ID and metadata dictionary.
* **Collection Resource (`@Collection`)**: A resource containing a dictionary of NFTs. Stored in account storage.
* **Account Storage Map**:
  * Collection stored at: `/storage/CreativeStudioNFTCollection`
  * Public capability exposed at: `/public/CreativeStudioNFTCollection` (linked to `CollectionPublic` interface)
  * Minter (admin resource) stored at: `/storage/CreativeStudioNFTMinter`

---

## Stage 3: Planning (Defining interface, storage paths, events)
We define the structure of our contract, interfaces, paths, and events:
* **Events**:
  * `ContractInitialized`
  * `Withdraw(id: UInt64, from: Address?)`
  * `Deposit(id: UInt64, to: Address?)`
  * `Minted(id: UInt64, creator: Address, url: String)`
* **Interfaces**:
  * `CollectionPublic`: Defines what functions are exposed to the public: `deposit`, `getIDs`, `borrowNFT`, and `borrowCreativeStudioNFT`.
* **Minter Resource**:
  * Exposed only to the admin/creator account to execute minting transactions.

---

## Stage 4: Build (Writing and verifying Cadence code)
The smart contract code will be written in `CreativeStudioNFT.cdc` using Cadence 1.0 syntax:
* Using `access(all)` instead of `pub`
* Entitlements for secure borrowing/withdrawing
* Event emissions on actions
