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

import {Injectable} from '@angular/core';
import {UserModel} from '../models/user.model';
import {environment} from '../../../environments/environment';
import {HttpClient} from '@angular/common/http';
import {Observable} from 'rxjs';

interface LooseObject {
  [key: string]: any;
}

const badgeURL = `${environment.backendURL}/`;

@Injectable({
  providedIn: 'root',
})
export class UserService {
  constructor(private http: HttpClient) {}

  get(id: number): Observable<UserModel> {
    return this.http.get<UserModel>(`${environment.backendURL}/users/${id}`);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${environment.backendURL}/users/${id}`);
  }

  searchUsers(query: string): Observable<UserModel[]> {
    return this.http.get<UserModel[]>(`${environment.backendURL}/users`, { params: { filter: query } });
  }

  // Deprecated: Use AuthService.getUser() or AuthService.getCurrentUserValue()
  // Keeping for compatibility if needed, but better to refactor consumers
  getUserDetails(): UserModel | null {
    const userStr = localStorage.getItem('USER_DETAILS');
    if (userStr) {
      return JSON.parse(userStr) as UserModel;
    }
    return null;
  }

  getUserBadges(userEmail: string) {
    return this.http.post<any>(badgeURL + 'badge-info', {email: userEmail});
  }

  updateBadgeInfo(reqObj: LooseObject) {
    return this.http.post<any>(badgeURL + 'badge-confetti-status', reqObj);
  }
}
