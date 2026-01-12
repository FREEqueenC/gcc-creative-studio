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
} from 'rxjs/operators';
import {MatSnackBar} from '@angular/material/snack-bar';
import { Workspace } from '../../common/models/workspace.model';
import { WorkspaceService } from '../../services/workspace/workspace.service';
import { OrganizationService } from '../../services/organization/organization.service';
import { Organization } from '../../common/models/organization.model';

@Component({
  selector: 'app-workspaces-management',
  templateUrl: './workspaces-management.component.html',
  styleUrls: ['./workspaces-management.component.scss'],
})
export class WorkspacesManagementComponent implements OnInit, OnDestroy {
  displayedColumns: string[] = [
    'name',
    'organization',
    'createdAt',
    'updatedAt',
  ];
  dataSource: MatTableDataSource<Workspace> =
    new MatTableDataSource<Workspace>();
  isLoading = true;
  errorLoadingWorkspaces: string | null = null;

  // --- Pagination State ---
  totalWorkspaces = 0;
  limit = 10;
  currentPageIndex = 0;

  // --- Filtering & Destroy State ---
  private filterSubject = new Subject<string>();
  private destroy$ = new Subject<void>();
  currentFilter = '';
  selectedOrganizationId: number | null = null;
  organizations: Organization[] = [];

  @ViewChild(MatPaginator) paginator!: MatPaginator;
  @ViewChild(MatSort) sort!: MatSort;

  constructor(
    private workspaceService: WorkspaceService,
    private organizationService: OrganizationService,
    private _snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    this.fetchPage(0);
    this.loadOrganizations();

    // Debounce filter input
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

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  handlePageEvent(event: PageEvent) {
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
        this.workspaceService.listAllWorkspaces(
          this.limit,
          offset,
          this.currentFilter,
          this.selectedOrganizationId || undefined
        )
      );

      this.dataSource.data = finalResponse.data;
      this.totalWorkspaces = finalResponse.count;
      this.currentPageIndex = targetPageIndex;
    } catch (err) {
      this.errorLoadingWorkspaces = 'Failed to load workspaces.';
      console.error(err);
    } finally {
      this.isLoading = false;
    }
  }

  applyFilter(event: Event): void {
    const filterValue = (event.target as HTMLInputElement).value;
    this.filterSubject.next(filterValue.trim());
  }

  onOrganizationChange() {
    this.resetPaginationAndFetch();
  }

  private resetPaginationAndFetch() {
    this.currentPageIndex = 0;
    if (this.paginator) {
      this.paginator.pageIndex = 0;
    }
    this.fetchPage(0);
  }
}
