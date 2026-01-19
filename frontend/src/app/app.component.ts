/**
 * Copyright 2025 Google LLC
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

import {Component} from '@angular/core';
import {Router, NavigationEnd, Event as NavigationEvent} from '@angular/router';
import {trigger, transition, style, query, animate} from '@angular/animations';
import {LoadingService} from './common/services/loading.service';
import {AuthService} from './common/services/auth.service';

import { MatSnackBar } from '@angular/material/snack-bar';
import { WorkspaceStateService } from './services/workspace/workspace-state.service';
import { handleErrorSnackbar } from './utils/handleMessageSnackbar';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
  animations: [
    trigger('routeAnimations', [
      transition('* <=> *', [
        style({position: 'relative'}),
        query(
          ':enter, :leave',
          [
            style({
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
            }),
          ],
          {optional: true},
        ),
        query(':enter', [style({opacity: 0})], {optional: true}),
        query(':leave', [animate('200ms ease-out', style({opacity: 0}))], {
          optional: true,
        }),
        query(':enter', [animate('300ms ease-in', style({opacity: 1}))], {
          optional: true,
        }),
      ]),
    ]),
  ],
})
export class AppComponent {
  title = 'creative-studio';
  showHeader = true;

  constructor(
    private router: Router,
    public loadingService: LoadingService,
    private authService: AuthService,
    private workspaceStateService: WorkspaceStateService,
    private snackBar: MatSnackBar
  ) {
    // Fetch user on init
    this.authService.getUser().subscribe();

    this.router.events.subscribe((event: NavigationEvent) => {
      if (event instanceof NavigationEnd) {
        if (
          event.url === '/login' ||
          event.url === '/login/e2e' ||
          (event.url.includes('login') && event.url.includes('email')) ||
          (event.url.includes('login') && event.url.includes('tos')) ||
          event.url.includes('reset-password') ||
          event.url.includes('support-ticket')
        ) {
          this.showHeader = false;
        } else {
          this.showHeader = true;
        }
      }
    });

    // Check permissions on workspace switch
    this.workspaceStateService.activeWorkspace$.subscribe(workspace => {
      if (!workspace) return;
      
      // If we are on the workflows page and don't have permission, redirect
      if (this.router.url.includes('/workflows')) {
        if (!workspace.permissions?.canViewWsWorkflows) {
           // Use setTimeout to ensure navigation happens after any current change detection or pending navigations
           setTimeout(() => {
             this.router.navigate(['/']);
           });
           handleErrorSnackbar(
             this.snackBar,
             { message: 'You do not have permission to view workflows in this workspace.' },
             'Access Denied'
           );
        }
      }
    });
  }
}
