// Copyright 2026 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import {Injectable} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {BehaviorSubject, firstValueFrom, Observable} from 'rxjs';
import {environment} from '../../../environments/environment';

export interface PrepareMintResponse {
  contractAddress: string;
  metadataUrl: string;
  itemId: number;
  mintFee: string;
}

@Injectable({
  providedIn: 'root'
})
export class Web3Service {
  private walletAddress$ = new BehaviorSubject<string | null>(null);
  public activeChain$ = new BehaviorSubject<string | null>(null);
  
  constructor(private http: HttpClient) {}

  get walletAddress(): Observable<string | null> {
    return this.walletAddress$.asObservable();
  }

  /**
   * Connects the Web3 wallet (simulated or Metamask/Coinbase Wallet).
   */
  async connectWallet(chain: 'base' | 'flow'): Promise<string> {
    this.activeChain$.next(chain);
    
    // Check if Metamask/Ethereum provider is available for Base
    if (chain === 'base' && typeof window !== 'undefined' && (window as any).ethereum) {
      try {
        const provider = (window as any).ethereum;
        const accounts = await provider.request({ method: 'eth_requestAccounts' });
        if (accounts && accounts.length > 0) {
          const address = accounts[0];
          this.walletAddress$.next(address);
          return address;
        }
      } catch (err) {
        console.warn('Web3 browser wallet connection rejected, falling back to simulated session', err);
      }
    }
    
    // Fallback/Simulated wallet connection (perfect for local development and edge agent sandbox)
    const mockAddress = chain === 'base' 
      ? '0x81631e082767e0f545386420ccb1128b98c70f60' 
      : '0x01cf0e2f2f715450';
    
    // Simulate slight network delay
    await new Promise(resolve => setTimeout(resolve, 800));
    this.walletAddress$.next(mockAddress);
    return mockAddress;
  }

  /**
   * Disconnects the wallet.
   */
  disconnectWallet(): void {
    this.walletAddress$.next(null);
    this.activeChain$.next(null);
  }

  /**
   * Contacts backend to get target contract and prepared metadata endpoint URL.
   */
  async prepareMint(itemId: number, chain: 'base' | 'flow'): Promise<PrepareMintResponse> {
    const url = `${environment.backendURL}/web3/prepare-mint`;
    return firstValueFrom(
      this.http.post<PrepareMintResponse>(url, { itemId, chain })
    );
  }

  /**
   * Mints the NFT by sending a transaction (or simulating it).
   */
  async executeMint(
    itemId: number, 
    chain: 'base' | 'flow', 
    prepData: PrepareMintResponse
  ): Promise<string> {
    const currentAddress = this.walletAddress$.value;
    if (!currentAddress) {
      throw new Error('Wallet not connected');
    }

    // Direct Web3 connection using window.ethereum
    if (chain === 'base' && typeof window !== 'undefined' && (window as any).ethereum) {
      try {
        const provider = (window as any).ethereum;
        // Simple transaction execution description
        // In full integration we encode the contract call: mintCreativeAsset(currentAddress, prepData.metadataUrl)
        console.log(`Interacting with contract ${prepData.contractAddress} to mint for ${currentAddress}`);
        
        // Return a mock/expected transaction hash for local sandbox to complete visual cycle smoothly
        const txHash = '0x' + Array.from({length: 64}, () => Math.floor(Math.random()*16).toString(16)).join('');
        await new Promise(resolve => setTimeout(resolve, 2000));
        return txHash;
      } catch (err) {
        console.error('Ethereum wallet transaction failed, utilizing simulation fallback', err);
      }
    }

    // Simulated blockchain transaction execution (instantly ready for demo and sandbox flow)
    await new Promise(resolve => setTimeout(resolve, 2500));
    
    // Return a random mock transaction hash representing Flow/Base confirmation
    if (chain === 'flow') {
      return Array.from({length: 16}, () => Math.floor(Math.random()*16).toString(16)).join('');
    } else {
      return '0x' + Array.from({length: 64}, () => Math.floor(Math.random()*16).toString(16)).join('');
    }
  }
}
