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

import {Component, Inject, OnInit} from '@angular/core';
import {MAT_DIALOG_DATA, MatDialogRef} from '@angular/material/dialog';
import {
  Web3Service,
  PrepareMintResponse,
} from '../../services/web3/web3.service';
import {GalleryItem} from '../../common/models/gallery-item.model';

export interface MintDialogData {
  mediaItem: GalleryItem;
}

@Component({
  selector: 'app-mint-dialog',
  templateUrl: './mint-dialog.component.html',
  styleUrls: ['./mint-dialog.component.scss'],
})
export class MintDialogComponent implements OnInit {
  public step:
    | 'select-chain'
    | 'connect-wallet'
    | 'confirm-mint'
    | 'minting'
    | 'success' = 'select-chain';
  public selectedChain: 'base' | 'flow' | null = null;
  public walletAddress: string | null = null;
  public prepData: PrepareMintResponse | null = null;
  public txHash: string | null = null;
  public errorMessage: string | null = null;

  constructor(
    public dialogRef: MatDialogRef<MintDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: MintDialogData,
    private web3Service: Web3Service,
  ) {}

  ngOnInit() {
    this.web3Service.walletAddress.subscribe(addr => {
      this.walletAddress = addr;
      if (addr && this.step === 'connect-wallet') {
        void this.loadPrepData();
      }
    });
  }

  selectChain(chain: 'base' | 'flow') {
    this.selectedChain = chain;
    if (this.walletAddress) {
      void this.loadPrepData();
    } else {
      this.step = 'connect-wallet';
    }
  }

  async connectWallet() {
    if (!this.selectedChain) return;
    try {
      this.errorMessage = null;
      await this.web3Service.connectWallet(this.selectedChain);
    } catch (err) {
      this.errorMessage = (err as Error).message || 'Failed to connect wallet';
    }
  }

  async loadPrepData() {
    if (!this.selectedChain || !this.data.mediaItem.id) return;
    try {
      this.step = 'minting'; // loading state
      this.errorMessage = null;
      this.prepData = await this.web3Service.prepareMint(
        this.data.mediaItem.id,
        this.selectedChain,
      );
      this.step = 'confirm-mint';
    } catch (err) {
      this.errorMessage =
        (err as {error?: {detail?: string}}).error?.detail ||
        'Failed to load mint parameters';
      this.step = 'select-chain';
    }
  }

  async confirmMint() {
    if (!this.selectedChain || !this.prepData || !this.data.mediaItem.id)
      return;
    try {
      this.step = 'minting';
      this.errorMessage = null;
      this.txHash = await this.web3Service.executeMint(
        this.data.mediaItem.id,
        this.selectedChain,
        this.prepData,
      );
      this.step = 'success';
    } catch (err) {
      this.errorMessage =
        (err as Error).message || 'Transaction failed or rejected';
      this.step = 'confirm-mint';
    }
  }

  close() {
    this.dialogRef.close();
  }

  getExplorerLink(): string {
    if (!this.txHash || !this.selectedChain) return '';
    return this.selectedChain === 'base'
      ? `https://basescan.org/tx/${this.txHash}`
      : `https://flowscan.org/transaction/${this.txHash}`;
  }
}
