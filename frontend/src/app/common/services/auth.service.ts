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

import {Injectable, Inject, PLATFORM_ID} from '@angular/core';
import {Router} from '@angular/router';
import {HttpClient} from '@angular/common/http';
import {environment} from '../../../environments/environment';
import {BehaviorSubject, Observable, of} from 'rxjs';
import {catchError, tap} from 'rxjs/operators';
import {isPlatformBrowser} from '@angular/common';
import {UserModel, UserRolesEnum} from '../models/user.model';

const USER_DETAILS = 'USER_DETAILS';
const LOGIN_ROUTE = '/login';

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private currentUserSubject = new BehaviorSubject<UserModel | null>(null);
  public currentUser$ = this.currentUserSubject.asObservable();

  constructor(
    private router: Router,
    private httpClient: HttpClient,
    @Inject(PLATFORM_ID) private platformId: Object
  ) {
    this.loadUserFromStorage();
  }

  login() {
    if (isPlatformBrowser(this.platformId)) {
      window.location.href = `${environment.backendURL}/login/google`;
    }
  }

  logout() {
    this.httpClient.get(`${environment.backendURL}/logout`).subscribe({
      next: () => {
        this.clearSession();
        this.router.navigate([LOGIN_ROUTE]);
      },
      error: (err) => {
        console.error('Logout failed', err);
        this.clearSession();
        this.router.navigate([LOGIN_ROUTE]);
      }
    });
  }

  getUser(): Observable<UserModel | null> {
    return this.httpClient.get<UserModel>(`${environment.backendURL}/me`).pipe(
      tap((user) => {
        this.currentUserSubject.next(user);
        if (isPlatformBrowser(this.platformId)) {
          localStorage.setItem(USER_DETAILS, JSON.stringify(user));
        }
      }),
      catchError((err) => {
        console.error('Failed to fetch user', err);
        this.currentUserSubject.next(null);
        if (isPlatformBrowser(this.platformId)) {
          localStorage.removeItem(USER_DETAILS);
        }
        return of(null);
      })
    );
  }

  private loadUserFromStorage() {
    if (isPlatformBrowser(this.platformId)) {
      const userStr = localStorage.getItem(USER_DETAILS);
      if (userStr) {
        try {
          const user = JSON.parse(userStr);
          this.currentUserSubject.next(user);
        } catch (e) {
          console.error('Failed to parse user from storage', e);
          localStorage.removeItem(USER_DETAILS);
        }
      }
    }
  }

  private clearSession() {
    this.currentUserSubject.next(null);
    if (isPlatformBrowser(this.platformId)) {
      localStorage.removeItem(USER_DETAILS);
    }
  }

  isLoggedIn(): boolean {
    return !!this.currentUserSubject.value;
  }

  isUserAdmin(): boolean {
    const user = this.currentUserSubject.value;
    return user?.roles?.includes(UserRolesEnum.ADMIN) || false;
  }
  
  // Helper to get current value synchronously if needed
  getCurrentUserValue(): UserModel | null {
    return this.currentUserSubject.value;
  }
}
