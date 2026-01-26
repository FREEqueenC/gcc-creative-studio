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

import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

// TODO: Define interfaces for the API responses
export interface TokenUsage {
  // Define structure based on backend response
}

export interface TokenBudgets {
  // Define structure based on backend response
}

export interface ActiveRoles {
  // Define structure based on backend response
}

export interface OrganizationUsage {
  // Define structure based on backend response
}

export interface UserUsageItem {
  date: string;
  category: string;
  spend: number;
}
export type UserUsage = UserUsageItem[];

export interface AssignedCreditsOverTime {
  date: string;
  total_assigned: number;
}

@Injectable({
  providedIn: 'root'
})
export class AnalyticsService {
  private readonly apiUrl = `${environment.backendURL}/analytics`;

  constructor(private http: HttpClient) { }

  getAdminAssignedOverTime(): Observable<AssignedCreditsOverTime[]> {
    return this.http.get<AssignedCreditsOverTime[]>(`${environment.backendURL}/credits/admin/assigned-over-time`);
  }

  getTokenUsage(): Observable<TokenUsage> {
    return this.http.get<TokenUsage>(`${this.apiUrl}/token-usage`);
  }

  getTokenBudgets(): Observable<TokenBudgets> {
    return this.http.get<TokenBudgets>(`${this.apiUrl}/token-budgets`);
  }

  getActiveRoles(): Observable<ActiveRoles> {
    return this.http.get<ActiveRoles>(`${this.apiUrl}/active-roles`);
  }

  getOrganizationUsage(orgId: number): Observable<OrganizationUsage> {
    return this.http.get<OrganizationUsage>(`${this.apiUrl}/organizations/${orgId}/usage`);
  }

  getUserUsage(userId: number): Observable<UserUsage> {
    return this.http.get<UserUsage>(`${this.apiUrl}/users/${userId}/usage`);
  }
}
