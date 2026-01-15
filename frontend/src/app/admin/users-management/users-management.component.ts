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

import {Component, OnInit, OnDestroy, ViewChild} from '@angular/core';
import {MatTableDataSource} from '@angular/material/table';
import {MatPaginator, PageEvent} from '@angular/material/paginator';
import {MatSort} from '@angular/material/sort';
import {Subject, firstValueFrom} from 'rxjs';
import {
  debounceTime,
  distinctUntilChanged,
  takeUntil,
  startWith,
  switchMap,
  map,
} from 'rxjs/operators';
import {UserService} from './user.service';
import {PaginatedResponse} from '../../common/models/pagination.model';
import {MatDialog} from '@angular/material/dialog';
import {UserFormComponent} from './user-form.component';
import {MatSnackBar} from '@angular/material/snack-bar';
import {UserModel, UserRolesEnum} from '../../common/models/user.model';
import { handleErrorSnackbar, handleSuccessSnackbar } from '../../utils/handleMessageSnackbar';
import { OrganizationService } from '../../services/organization/organization.service';
import { WorkspaceService } from '../../services/workspace/workspace.service';
import { Organization } from '../../common/models/organization.model';
import { Workspace } from '../../common/models/workspace.model';
import { FormControl } from '@angular/forms';
import { Observable, of } from 'rxjs';
import { AuthService } from '../../common/services/auth.service';

@Component({
  selector: 'app-users-management',
  templateUrl: './users-management.component.html',
  styleUrls: ['./users-management.component.scss'],
})
export class UsersManagementComponent implements OnInit, OnDestroy {
  displayedColumns: string[] = [
    'picture',
    'name',
    'email',
    'roles',
    'createdAt',
    'updatedAt',
    'actions',
  ];
  dataSource: MatTableDataSource<UserModel> =
    new MatTableDataSource<UserModel>();
  isLoading = true;
  errorLoadingUsers: string | null = null;
  lastResponse: PaginatedResponse<UserModel> | undefined;

  // --- Pagination State ---
  totalUsers = 0;
  limit = 10;
  currentPageIndex = 0;

  // --- Filtering & Destroy State ---
  private filterSubject = new Subject<string>();
  private destroy$ = new Subject<void>();
  currentFilter = '';
  
  // Filters
  selectedOrganizationId: number | null = null;
  selectedWorkspaceId: number | null = null;
  
  organizations: Organization[] = [];
  workspaces: Workspace[] = [];
  
  // Workspace Search
  workspaceSearchControl = new FormControl('');
  filteredWorkspaces$: Observable<Workspace[]> = of([]);

  @ViewChild(MatPaginator) paginator!: MatPaginator;
  @ViewChild(MatSort) sort!: MatSort;

  currentUser: UserModel | null = null;

  constructor(
    private userService: UserService,
    public dialog: MatDialog,
    private _snackBar: MatSnackBar,
    private organizationService: OrganizationService,
    private workspaceService: WorkspaceService,
    private authService: AuthService
  ) {
    this.authService.currentUser$.subscribe(user => {
      this.currentUser = user;
    });
  }

  ngOnInit(): void {
    this.fetchPage(0);
    this.loadOrganizations();
    this.loadWorkspaces();

    // Debounce filter input to avoid excessive Firestore reads
    this.filterSubject
      .pipe(debounceTime(500), distinctUntilChanged(), takeUntil(this.destroy$))
      .subscribe(filterValue => {
        this.currentFilter = filterValue;
        this.resetPaginationAndFetch();
      });
  }

  loadOrganizations() {
    this.organizationService.listOrganizations().subscribe(response => {
        this.organizations = response.data;
    });
  }

  loadWorkspaces() {
    // Initial load: Get all workspaces (or top N)
    // We'll use the existing getWorkspaces for initial population
    this.workspaceService.getWorkspaces().subscribe(workspaces => {
        this.workspaces = workspaces;
        // Initialize filteredWorkspaces with first 5
        this.filteredWorkspaces$ = this.workspaceSearchControl.valueChanges.pipe(
          startWith(''),
          debounceTime(300),
          distinctUntilChanged(),
          switchMap(query => {
            if (!query || typeof query !== 'string' || query.trim() === '') {
              // Return first 5 of loaded workspaces
              return of(this.workspaces.slice(0, 5));
            }
            if (query.trim().length < 3) {
               return of(this.workspaces.slice(0, 5));
            }
            // Perform server-side search
            return this.workspaceService.searchWorkspaces(query);
          })
        );
    });
  }

  onOrganizationChange(newVal: number | null) {
    console.log('onOrganizationChange:', newVal, typeof newVal);
    this.selectedOrganizationId = newVal;
    if (this.selectedOrganizationId != null) {
      this.selectedWorkspaceId = null; // Clear workspace filter
    }
    this.resetPaginationAndFetch();
  }

  onWorkspaceChange(newVal: number | null) {
    console.log('onWorkspaceChange:', newVal, typeof newVal);
    this.selectedWorkspaceId = newVal;
    if (this.selectedWorkspaceId != null) {
      this.selectedOrganizationId = null; // Clear organization filter
    }
    this.resetPaginationAndFetch();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  handlePageEvent(event: PageEvent) {
    // If page size changes, we must reset everything.
    if (this.limit !== event.pageSize) {
      this.limit = event.pageSize;
      this.resetPaginationAndFetch();
      return;
    }
    this.fetchPage(event.pageIndex);
  }

  async fetchPage(targetPageIndex: number) {
    this.isLoading = true;
    const offset = targetPageIndex * this.limit;

    try {
      const finalResponse = await firstValueFrom(
        this.userService.getUsers(
          this.limit,
          this.currentFilter,
          offset,
          this.selectedOrganizationId || undefined,
          this.selectedWorkspaceId || undefined
        ),
      );

      this.dataSource.data = finalResponse.data;
      this.totalUsers = finalResponse.count;
      this.currentPageIndex = targetPageIndex;
    } catch (err) {
      this.errorLoadingUsers = 'Failed to load users.';
      console.error(err);
    } finally {
      this.isLoading = false;
    }
  }

  applyFilter(event: Event): void {
    const filterValue = (event.target as HTMLInputElement).value;
    this.filterSubject.next(filterValue.trim().toLowerCase());
  }

  private resetPaginationAndFetch() {
    this.currentPageIndex = 0;
    if (this.paginator) {
      this.paginator.pageIndex = 0;
    }
    this.fetchPage(0);
  }

  openUserForm(user: UserModel): void {
    const dialogRef = this.dialog.open(UserFormComponent, {
      width: '450px',
      data: {user: user, isEditMode: true},
    });

    dialogRef
      .afterClosed()
      .pipe(takeUntil(this.destroy$))
      .subscribe(async (result: UserModel | undefined) => {
        if (result) {
          this.isLoading = true;
          try {
            // The form returns the full user object with updated roles
            await firstValueFrom(this.userService.updateUser(result));
            handleSuccessSnackbar(this._snackBar, 'User updated successfully!');
            // Refetch to show updated data on the current page.
            this.fetchPage(this.currentPageIndex);
          } catch (err) {
            console.error(`Error updating user ${result.id}:`, err);
            handleErrorSnackbar(this._snackBar, err, 'Update user');
          } finally {
            this.isLoading = false;
          }
        }
      });
  }

  async deleteUser(userId: string): Promise<void> {
    if (this.currentUser && this.currentUser.id === userId) {
      handleErrorSnackbar(this._snackBar, 'You cannot delete your own account.', 'Delete User');
      return;
    }

    // Simple confirmation, consider using a MatDialog for a better UX
    if (confirm(`Are you sure you want to delete user with ID: ${userId}?`)) {
      this.isLoading = true;
      try {
        await firstValueFrom(this.userService.deleteUser(userId));
        handleSuccessSnackbar(this._snackBar, 'User deleted successfully!');
        this.resetPaginationAndFetch();
      } catch (err) {
        console.error(`Error deleting user ${userId}:`, err);
        handleErrorSnackbar(this._snackBar, err, 'Delete user');
      } finally {
        this.isLoading = false;
      }
    }
  }

  public getRoleChipClass(role: string): string {
    const roleLower = role.toLowerCase();

    // Using a switch statement makes it easy to add more roles later
    switch (roleLower) {
      case 'admin':
      case UserRolesEnum.ADMIN.toLowerCase():
        return '!bg-amber-500/20 !text-amber-300';
      case 'editor':
        return '!bg-blue-500/20 !text-blue-300';
      case 'viewer':
      case 'member':
      case UserRolesEnum.USER.toLowerCase():
        return '!bg-gray-500/20 !text-gray-300';
      case UserRolesEnum.CREATOR.toLowerCase():
        return '!bg-purple-500/20 !text-purple-300';
      default:
        // It's good practice to have a default style
        return '!bg-gray-500/20 !text-gray-300';
    }
  }

  // --- Role Management ---

  get isContextSelected(): boolean {
    const selected = this.selectedOrganizationId != null || this.selectedWorkspaceId != null;
    // console.log('isContextSelected:', selected, 'Org:', this.selectedOrganizationId, 'WS:', this.selectedWorkspaceId);
    return selected;
  }

  get availableRoles(): string[] {
    if (this.selectedOrganizationId != null) {
      return ['admin', 'member'];
    } else if (this.selectedWorkspaceId != null) {
      return ['admin', 'editor', 'viewer'];
    }
    return [];
  }

  getContextRole(user: UserModel): string {
    if (this.selectedOrganizationId != null) {
      const org = user.organizations?.find(o => o.id === this.selectedOrganizationId);
      // console.log('getContextRole (Org):', user.name, this.selectedOrganizationId, org);
      return org?.role || 'member'; 
    } else if (this.selectedWorkspaceId != null) {
      const ws = user.workspaces?.find(w => w.id === this.selectedWorkspaceId);
      return ws?.role || 'viewer';
    }
    return user.roles?.[0] || 'user';
  }



  async changeRole(user: UserModel, newRole: string) {
    if (this.currentUser && this.currentUser.id === user.id) {
        handleErrorSnackbar(this._snackBar, 'You cannot change your own role.', 'Change Role');
        // Reset selection if possible, or just return. 
        // Since it's a select change, the UI might already show the new value. 
        // Ideally we should revert it, but for now just preventing the API call is key.
        // To revert, we'd need to reload or manually reset.
        this.fetchPage(this.currentPageIndex); // Reload to revert UI
        return;
    }

    console.log('changeRole called:', user.id, newRole, 'Org:', this.selectedOrganizationId, 'WS:', this.selectedWorkspaceId);
    if (!this.isContextSelected) {
      console.warn('changeRole: No context selected');
      return;
    }

    this.isLoading = true;
    try {
      if (this.selectedOrganizationId != null) {
        console.log('Updating Org Role...');
        await firstValueFrom(this.userService.updateOrganizationRole(this.selectedOrganizationId, Number(user.id), newRole));
      } else if (this.selectedWorkspaceId != null) {
        console.log('Updating Workspace Role...');
        await firstValueFrom(this.userService.updateWorkspaceRole(this.selectedWorkspaceId, Number(user.id), newRole));
      }
      
      handleSuccessSnackbar(this._snackBar, 'Role updated successfully!');
      // Update local state to reflect change immediately without full reload if possible, 
      // but fetching page is safer to ensure consistency.
      this.fetchPage(this.currentPageIndex);
    } catch (err) {
      console.error(`Error updating role for user ${user.id}:`, err);
      handleErrorSnackbar(this._snackBar, err, 'Update Role');
    } finally {
      this.isLoading = false;
    }
  }
}
