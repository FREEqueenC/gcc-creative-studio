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

import {Component, OnDestroy, Inject, PLATFORM_ID, ViewChild} from '@angular/core';
import {MatMenuTrigger} from '@angular/material/menu';
import {DomSanitizer, SafeResourceUrl} from '@angular/platform-browser';
import {MatIconRegistry} from '@angular/material/icon';
import {Router} from '@angular/router';
import {UserService} from '../common/services/user.service';
import {AuthService} from '../common/services/auth.service';
import {environment} from '../../environments/environment';
import {UserModel} from '../common/models/user.model';
import {animate, style, transition, trigger} from '@angular/animations';
import {BreakpointObserver, Breakpoints} from '@angular/cdk/layout';
import {Subject, Observable, of} from 'rxjs';
import {takeUntil, switchMap, shareReplay, map} from 'rxjs/operators';
import {isPlatformBrowser} from '@angular/common';

import {WorkspaceStateService} from '../services/workspace/workspace-state.service';

@Component({
  selector: 'app-header',
  templateUrl: './header.component.html',
  styleUrls: ['./header.component.scss'],
  animations: [
    trigger('fadeSlideInOut', [
      transition(':enter', [
        style({opacity: 0, transform: 'translateY(-10px)'}),
        animate(
          '300ms ease-in-out',
          style({opacity: 1, transform: 'translateY(0)'}),
        ),
      ]),
      transition(':leave', [
        animate(
          '300ms ease-in-out',
          style({opacity: 0, transform: 'translateY(-10px)'}),
        ),
      ]),
    ]),
  ],
})
export class HeaderComponent implements OnDestroy {
  currentUser: UserModel | null;
  menuFixed = false;
  menuIsHovered = false;
  isAdmin$: Observable<boolean>;
  canViewWorkflows$: Observable<boolean>;

  isDesktop = false;
  private readonly destroy$ = new Subject<void>();
  toolsMenuHovered = false;
  profileMenuHovered = false;
  private toolsMenuTimeout: any;
  private profileMenuTimeout: any;
  isBrowser: boolean;
  @ViewChild('menuTrigger') menuTrigger!: MatMenuTrigger;

  constructor(
    private sanitizer: DomSanitizer,
    public matIconRegistry: MatIconRegistry,
    public router: Router,
    public userService: UserService,
    public authService: AuthService,
    private breakpointObserver: BreakpointObserver,
    private workspaceStateService: WorkspaceStateService,
    @Inject(PLATFORM_ID) platformId: Object
  ) {
    this.isBrowser = isPlatformBrowser(platformId);
    // Initialize menuFixed from localStorage
    if (this.isBrowser) {
        const storedMenuFixed = localStorage.getItem('menuFixed');
        this.menuFixed = storedMenuFixed === 'true';
    }

    this.matIconRegistry
      .addSvgIcon(
        'creative-studio-icon',
        this.setPath(`${this.path}/creative-studio-icon.svg`),
      )
      .addSvgIcon(
        'fun-templates-icon',
        this.setPath(`${this.path}/fun-templates-icon.svg`),
      )
      .addSvgIcon(
        'audio-generation-icon',
        this.setPath(`${this.path}/audio-generation-icon.svg`),
      );

    this.currentUser = this.userService.getUserDetails();

    this.isAdmin$ = this.authService.currentUser$.pipe(
      switchMap(user => {
        if (!user) return of(false);
        // Use the flag returned by the backend
        return of(!!user.canAccessAdminPanel);
      }),
      shareReplay(1)
    );

    this.breakpointObserver
      .observe([Breakpoints.Medium, Breakpoints.Large, Breakpoints.XLarge])
      .pipe(takeUntil(this.destroy$))
      .subscribe(result => {
        this.isDesktop = result.matches;
      });
      
    this.canViewWorkflows$ = this.workspaceStateService.activeWorkspace$.pipe(
      map(workspace => {
        if (!workspace) return false;

        return workspace.permissions?.canViewWsWorkflows ?? false;
      })
    );
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  private path = '../../assets/images';

  private setPath(url: string): SafeResourceUrl {
    return this.sanitizer.bypassSecurityTrustResourceUrl(url);
  }

  logout() {
    void this.authService.logout();
  }

  navigate() {
    void this.router.navigateByUrl('/');
  }

  toggleMenu() {
    this.menuFixed = !this.menuFixed;
    localStorage.setItem('menuFixed', String(this.menuFixed));
  }

  getTooltipText() {
    return this.menuFixed
      ? `Hey there ${this.currentUser?.name?.split(' ')?.[0] || ''}! Click to make the menu dynamic`
      : 'Click to make the menu fixed';
  }

  onToolsEnter() {
    // If we enter the area, cancel any pending close action
    if (this.toolsMenuTimeout) {
      clearTimeout(this.toolsMenuTimeout);
    }
    this.toolsMenuHovered = true;
  }

  onToolsLeave() {
    // When leaving, wait 200ms before actually closing.
    // If the user enters the menu during this time, onToolsEnter()
    // will cancel this timer, keeping the menu open.
    this.toolsMenuTimeout = setTimeout(() => {
      this.toolsMenuHovered = false;
    }, 200);
  }

  openFeedbackForm(): void {
    if (this.isBrowser) {
        window.open(
        'https://docs.google.com/forms/d/e/1FAIpQLSceWvu7G354h-dTbOGvNGEraEjcUAgPE300WNY5qr-WJbh3Eg/viewform',
        '_blank',
        );
    }
  }

  openProfileMenu() {
    if (this.profileMenuTimeout) {
      clearTimeout(this.profileMenuTimeout);
      this.profileMenuTimeout = null;
    }
    if (this.menuTrigger && !this.menuTrigger.menuOpen) {
      this.menuTrigger.openMenu();
    }
  }

  closeProfileMenu() {
    if (!this.profileMenuTimeout) {
      this.profileMenuTimeout = setTimeout(() => {
        if (this.menuTrigger) {
          this.menuTrigger.closeMenu();
        }
        this.profileMenuTimeout = null;
      }, 200);
    }
  }

  onProfileEnter() {
    if (this.profileMenuTimeout) {
      clearTimeout(this.profileMenuTimeout);
    }
    this.profileMenuHovered = true;
  }

  onProfileLeave() {
    this.profileMenuTimeout = setTimeout(() => {
      this.profileMenuHovered = false;
    }, 200);
  }
}
