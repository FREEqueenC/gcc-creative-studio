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
import {
  HttpClient,
  HttpHeaders,
  HttpErrorResponse,
  HttpParams,
} from '@angular/common/http';
import {Observable, throwError} from 'rxjs';
import {catchError, tap} from 'rxjs/operators';
import {environment} from '../../../environments/environment'; // To get backendURL
import {UserModel} from '../../common/models/user.model';

import {PaginatedResponse} from '../../common/models/pagination.model';

// export interface PaginatedResponse { ... } // Removed local definition

@Injectable({
  providedIn: 'root', // Or provide it specifically in AdminModule if preferred
})
export class UserService {
  // Define the structure of the paginated response from the backend
  private usersApiUrl = `${environment.backendURL}/users`;

  private httpOptions = {
    headers: new HttpHeaders({
      'Content-Type': 'application/json',
    }),
  };

  constructor(private http: HttpClient) {}

  // GET: Fetch all users
  getUsers(
    limit: number,
    filter: string,
    offset?: number,
    organizationId?: number,
    workspaceId?: number,
  ): Observable<PaginatedResponse<UserModel>> {
    let params = new HttpParams()
      .set('limit', limit.toString())
      .set('email', filter);

    if (offset !== undefined) params = params.set('offset', offset.toString());
    if (organizationId !== undefined && organizationId !== null) params = params.set('organizationId', organizationId.toString());
    if (workspaceId !== undefined && workspaceId !== null) params = params.set('workspaceId', workspaceId.toString());

    return this.http
      .get<PaginatedResponse<UserModel>>(this.usersApiUrl, {params, ...this.httpOptions})
      .pipe(catchError(this.handleError));
  }

  // GET: Fetch a single user by ID
  getUser(id: number | string): Observable<UserModel> {
    const url = `${this.usersApiUrl}/${id}`;
    return this.http
      .get<UserModel>(url, this.httpOptions)
      .pipe(catchError(this.handleError));
  }

  // POST: Add a new user
  addUser(user: UserModel): Observable<UserModel> {
    return this.http
      .post<UserModel>(this.usersApiUrl, user, this.httpOptions)
      .pipe(catchError(this.handleError));
  }

  // PUT: Update an existing user
  updateUser(user: UserModel): Observable<any> {
    // FastAPI might return the updated user or just a success status
    const url = `${this.usersApiUrl}/${user.id}`;
    // The backend expects UserUpdateRoleDto which only has 'roles'
    const payload = {roles: user.roles};
    return this.http
      .put(url, payload, this.httpOptions)
      .pipe(catchError(this.handleError));
  }

  // DELETE: Delete a user
  deleteUser(id: number | string): Observable<UserModel> {
    // Or Observable<{}> if backend returns empty on delete
    const url = `${this.usersApiUrl}/${id}`;
    return this.http
      .delete<UserModel>(url, this.httpOptions)
      .pipe(catchError(this.handleError));
  }

  // PUT: Update Organization Role
  updateOrganizationRole(orgId: number, userId: number, role: string): Observable<any> {
    const url = `${environment.backendURL}/organizations/${orgId}/users/${userId}/role`;
    const payload = { role };
    return this.http
      .put(url, payload, this.httpOptions)
      .pipe(catchError(this.handleError));
  }

  // PUT: Update Workspace Role
  updateWorkspaceRole(workspaceId: number, userId: number, role: string): Observable<any> {
    const url = `${environment.backendURL}/workspaces/${workspaceId}/users/${userId}/role`;
    const payload = { role };
    return this.http
      .put(url, payload, this.httpOptions)
      .pipe(catchError(this.handleError));
  }

  // PUT: Update Super Admin Status
  updateSuperAdminStatus(userId: number, isSuperAdmin: boolean): Observable<any> {
    const url = `${this.usersApiUrl}/${userId}/super-admin`;
    const payload = { is_super_admin: isSuperAdmin };
    return this.http
      .put(url, payload, this.httpOptions)
      .pipe(catchError(this.handleError));
  }

  // Basic error handling
  private handleError(error: HttpErrorResponse) {
    // Pass the raw error to the component so handleMessageSnackbar can parse it
    return throwError(() => error);
  }
}
