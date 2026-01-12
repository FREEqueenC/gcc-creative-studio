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
import { Organization } from '../../common/models/organization.model';
import { OrganizationService } from '../../services/organization/organization.service';
import { PaginatedResponse } from '../../common/models/pagination.model';

@Component({
  selector: 'app-organizations-management',
  templateUrl: './organizations-management.component.html',
  styleUrls: ['./organizations-management.component.scss'],
})
export class OrganizationsManagementComponent implements OnInit, OnDestroy {
  displayedColumns: string[] = [
    'name',
    'domain',
    'createdAt',
    'updatedAt',
  ];
  dataSource: MatTableDataSource<Organization> =
    new MatTableDataSource<Organization>();
  isLoading = true;
  errorLoadingOrgs: string | null = null;

  // --- Pagination State ---
  totalOrgs = 0;
  limit = 10;
  currentPageIndex = 0;

  // --- Filtering & Destroy State ---
  private filterSubject = new Subject<string>();
  private destroy$ = new Subject<void>();
  currentFilter = '';

  @ViewChild(MatPaginator) paginator!: MatPaginator;
  @ViewChild(MatSort) sort!: MatSort;

  constructor(
    private organizationService: OrganizationService,
    private _snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    this.fetchPage(0);

    // Debounce filter input
    this.filterSubject
      .pipe(debounceTime(500), distinctUntilChanged(), takeUntil(this.destroy$))
      .subscribe(filterValue => {
        this.currentFilter = filterValue;
        this.resetPaginationAndFetch();
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
        this.organizationService.listOrganizations(
          this.limit,
          offset,
          this.currentFilter
        )
      );

      this.dataSource.data = finalResponse.data;
      this.totalOrgs = finalResponse.count;
      this.currentPageIndex = targetPageIndex;
    } catch (err) {
      this.errorLoadingOrgs = 'Failed to load organizations.';
      console.error(err);
    } finally {
      this.isLoading = false;
    }
  }

  applyFilter(event: Event): void {
    const filterValue = (event.target as HTMLInputElement).value;
    this.filterSubject.next(filterValue.trim());
  }

  private resetPaginationAndFetch() {
    this.currentPageIndex = 0;
    if (this.paginator) {
      this.paginator.pageIndex = 0;
    }
    this.fetchPage(0);
  }
}
