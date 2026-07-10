/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import {
  Component,
  OnInit,
  ViewChild,
  ElementRef,
  AfterViewChecked,
} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {environment} from '../../environments/environment';
import {MatSnackBar} from '@angular/material/snack-bar';
import {handleErrorSnackbar} from '../utils/handleMessageSnackbar';

interface ChatMessage {
  role: 'user' | 'model';
  content: string;
}

@Component({
  selector: 'app-docs',
  templateUrl: './docs.component.html',
  styleUrls: ['./docs.component.scss'],
})
export class DocsComponent implements OnInit, AfterViewChecked {
  @ViewChild('chatScrollContainer') private chatScrollContainer!: ElementRef;

  categories = [
    {id: 'overview', title: 'Studio Overview', icon: 'explore'},
    {id: 'setup', title: 'Local Setup', icon: 'settings'},
    {id: 'web3', title: 'Web3 & NFTs', icon: 'account_balance_wallet'},
    {id: 'agents', title: 'Edge Agent APIs', icon: 'smart_toy'},
  ];

  selectedCategoryId = 'overview';
  chatMessages: ChatMessage[] = [];
  userInput = '';
  isChatLoading = false;

  constructor(
    private http: HttpClient,
    private snackBar: MatSnackBar,
  ) {}

  ngOnInit(): void {
    // Initial welcome message from the agent
    this.chatMessages.push({
      role: 'model',
      content:
        'Hello! I am the Aetheris X AI Developer Support Agent. Ask me anything about the local setup, API routes, or Web3 integration!',
    });
  }

  ngAfterViewChecked() {
    this.scrollToBottom();
  }

  selectCategory(categoryId: string) {
    this.selectedCategoryId = categoryId;
  }

  sendMessage() {
    if (!this.userInput.trim() || this.isChatLoading) {
      return;
    }

    const userMsg = this.userInput.trim();
    this.chatMessages.push({role: 'user', content: userMsg});
    this.userInput = '';
    this.isChatLoading = true;

    const payload = {
      message: userMsg,
      history: this.chatMessages.slice(0, -1), // Exclude the message we just added
    };

    this.http
      .post<{
        response: string;
      }>(`${environment.backendURL}/gemini/docs-chat`, payload)
      .subscribe({
        next: res => {
          this.isChatLoading = false;
          this.chatMessages.push({role: 'model', content: res.response});
        },
        error: err => {
          this.isChatLoading = false;
          handleErrorSnackbar(this.snackBar, err, 'AI Docs Agent');
          this.chatMessages.push({
            role: 'model',
            content:
              'Sorry, I encountered an error communicating with the agent server. Please try again.',
          });
        },
      });
  }

  private scrollToBottom(): void {
    try {
      this.chatScrollContainer.nativeElement.scrollTop =
        this.chatScrollContainer.nativeElement.scrollHeight;
    } catch (err) {
      // Silently ignore errors when scrolling container is not available
    }
  }
}
