access(all) contract CreativeStudioNFT {

    access(all) event ContractInitialized()
    access(all) event Withdraw(id: UInt64, from: Address?)
    access(all) event Deposit(id: UInt64, to: Address?)
    access(all) event Minted(id: UInt64, creator: Address, url: String)

    access(all) entitlement WithdrawEntitlement

    access(all) resource interface CollectionPublic {
        access(all) fun deposit(token: @NFT)
        access(all) fun getIDs(): [UInt64]
        access(all) fun borrowNFT(id: UInt64): &NFT
        access(all) fun borrowCreativeStudioNFT(id: UInt64): &CreativeStudioNFT.NFT? {
            post {
                result == nil || result!.id == id: "The returned reference must match the requested ID"
            }
        }
    }

    access(all) resource NFT {
        access(all) let id: UInt64
        access(all) let metadata: {String: String}

        init(id: UInt64, metadata: {String: String}) {
            self.id = id
            self.metadata = metadata
        }
    }

    access(all) resource Collection: CollectionPublic {
        access(all) var ownedNFTs: @{UInt64: NFT}

        init() {
            self.ownedNFTs <- {}
        }

        // Withdraw removes an NFT from the collection and returns it
        access(WithdrawEntitlement) fun withdraw(withdrawID: UInt64): @NFT {
            let token <- self.ownedNFTs.remove(key: withdrawID)
                ?? panic("Could not withdraw: NFT does not exist in the collection")

            emit Withdraw(id: token.id, from: self.owner?.address)

            return <-token
        }

        // Deposit takes an NFT and adds it to the collection
        access(all) fun deposit(token: @NFT) {
            let id = token.id
            let oldToken <- self.ownedNFTs[id] <- token
            
            emit Deposit(id: id, to: self.owner?.address)

            destroy oldToken
        }

        // getIDs returns an array of the IDs that are in the collection
        access(all) fun getIDs(): [UInt64] {
            return self.ownedNFTs.keys
        }

        // borrowNFT gets a reference to an NFT in the collection
        access(all) fun borrowNFT(id: UInt64): &NFT {
            return (&self.ownedNFTs[id] as &NFT?)!
        }

        // borrowCreativeStudioNFT gets a reference to an NFT as a CreativeStudioNFT reference
        access(all) fun borrowCreativeStudioNFT(id: UInt64): &CreativeStudioNFT.NFT? {
            if self.ownedNFTs[id] != nil {
                let ref = (&self.ownedNFTs[id] as &NFT?)!
                return ref
            }
            return nil
        }
    }

    // public function to create a new empty Collection
    access(all) fun createEmptyCollection(): @Collection {
        return <-create Collection()
    }

    // resource for minting new NFTs
    access(all) resource Minter {
        access(all) var nextID: UInt64

        init() {
            self.nextID = 1
        }

        access(all) fun mintNFT(creator: Address, metadata: {String: String}): @NFT {
            let newNFT <- create NFT(id: self.nextID, metadata: metadata)
            emit Minted(id: self.nextID, creator: creator, url: metadata["url"] ?? "")
            self.nextID = self.nextID + 1
            return <-newNFT
        }
    }

    init() {
        self.account.storage.save(<-create Collection(), to: /storage/CreativeStudioNFTCollection)
        let cap = self.account.capabilities.storage.issue<&Collection>(/storage/CreativeStudioNFTCollection)
        self.account.capabilities.publish(cap, at: /public/CreativeStudioNFTCollection)

        self.account.storage.save(<-create Minter(), to: /storage/CreativeStudioNFTMinter)

        emit ContractInitialized()
    }
}
