import { Component, OnInit, ViewChild, ElementRef, AfterViewInit, OnDestroy } from '@angular/core';
import { handleErrorSnackbar, handleSuccessSnackbar } from '../../utils/handleMessageSnackbar';
import { AnalyticsService, TokenUsage, TokenBudgets, ActiveRoles, AssignedCreditsOverTime } from '../../common/services/analytics.service';
import * as d3 from 'd3';
import { AuthService } from '../../common/services/auth.service';
import { Observable, forkJoin, of, Subject } from 'rxjs';
import { catchError, debounceTime, distinctUntilChanged, switchMap, tap, filter, map, take, startWith } from 'rxjs/operators';
import { FormControl, FormGroup, Validators } from '@angular/forms';
import { UserService } from '../../common/services/user.service';
import { OrganizationService } from '../../services/organization/organization.service';
import { CreditsService, PriceCatalogDto, CreatePriceCatalogDto, UpdatePriceCatalogDto } from '../../services/credits/credits.service';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatDialog } from '@angular/material/dialog';
import { UserModel } from '../../common/models/user.model';
import { PaginatedResponse } from '../../common/models/pagination.model';
import { Organization } from '../../common/models/organization.model';
import { PriceCatalogDialogComponent, PriceCatalogDialogData } from './price-catalog-dialog.component';
import { ConfirmationDialogComponent } from '../../common/components/confirmation-dialog/confirmation-dialog.component';
@Component({
  selector: 'app-credits-analytics',
  templateUrl: './credits-analytics.component.html',
  styleUrls: ['./credits-analytics.component.scss']
})
export class CreditsAnalyticsComponent implements OnInit, AfterViewInit, OnDestroy {
  tokenUsage$: Observable<TokenUsage | null> | undefined;
  tokenBudgets$: Observable<TokenBudgets | null> | undefined;
  activeRoles$: Observable<ActiveRoles | null> | undefined;

  isSuperAdmin: boolean;

  // Credit Assignment Form
  assignForm = new FormGroup({
    targetType: new FormControl<'user' | 'org'>('user', [Validators.required]),
    targetUser: new FormControl<UserModel | null>(null),
    targetOrg: new FormControl<Organization | null>(null),
    amount: new FormControl<number>(0, [Validators.required, Validators.min(1)]),
    expirationDate: new FormControl<Date | null>(null)
  });

  // UserModel Search
  userSearchCtrl = new FormControl('');
  filteredUsers$: Observable<UserModel[]> | undefined;
  isLoadingUsers = false;

  // Org Search
  organizations$: Observable<Organization[]> | undefined;

  // Balance Check
  checkBalanceCtrl = new FormControl('');
  balanceResult: number | null = null;
  balanceCheckLoading = false;

  // Price Catalog
  priceCatalog$: Observable<PriceCatalogDto[]> | undefined;
  priceCatalogColumns: string[] = ['model_id', 'category', 'cost', 'updated_at', 'actions'];

  // Assigned Credits Chart
  @ViewChild('assignedCreditsChart') private assignedCreditsChartContainer!: ElementRef;
  assignedCreditsData$: Observable<AssignedCreditsOverTime[] | null> | undefined;
  constructor(
    private analyticsService: AnalyticsService,
    private authService: AuthService,
    private userService: UserService,
    private organizationService: OrganizationService,
    private creditsService: CreditsService,
    private snackBar: MatSnackBar,
    private dialog: MatDialog
  ) {
    this.isSuperAdmin = this.authService.isUserAdmin() ?? false;
  }

  ngOnInit(): void {
    this.loadGeneralAnalytics();
    this.loadOrganizations();
    this.loadPriceCatalog();
    this.loadAssignedCreditsData();

    const navigationState = window.history.state;
    console.log('CreditsAnalytics OnInit - navigationState:', navigationState);
    const userEmail = navigationState?.['userEmail'];
    console.log('CreditsAnalytics OnInit - userEmail from state:', userEmail);

    if (userEmail) {
      this.userSearchCtrl.setValue(userEmail);
      // Clear the state to prevent it from persisting on refresh or back navigation
      window.history.replaceState({...window.history.state, userEmail: undefined}, '');
    }

    this.setupUserSearch();

    const initialEmail = this.userSearchCtrl.value;
    if (typeof initialEmail === 'string' && initialEmail && this.filteredUsers$) {
      console.log('CreditsAnalytics OnInit - initialEmail for preselection:', initialEmail);
      this.filteredUsers$.pipe(
        take(1),
        filter(users => users && users.length > 0)
      ).subscribe(users => {
        console.log('CreditsAnalytics OnInit - filteredUsers$ emitted:', users);
        const matchingUser = users.find(u => u.email === initialEmail);
        console.log('CreditsAnalytics OnInit - matchingUser:', matchingUser);
        if (matchingUser) {
          setTimeout(() => {
            // Set the control value to the object for the autocomplete
            this.userSearchCtrl.setValue(matchingUser.email);
            // Patch the form group as well
            this.assignForm.patchValue({ targetUser: matchingUser, targetType: 'user' });
          });
        }
      });
    }
  }

  loadGeneralAnalytics(): void {
    this.tokenUsage$ = this.analyticsService.getTokenUsage().pipe(
      catchError(err => {
        console.error('Error loading token usage:', err);
        return of(null);
      })
    );
    this.tokenBudgets$ = this.analyticsService.getTokenBudgets().pipe(
      catchError(err => {
        console.error('Error loading token budgets:', err);
        return of(null);
      })
    );
    this.activeRoles$ = this.analyticsService.getActiveRoles().pipe(
      catchError(err => {
        console.error('Error loading active roles:', err);
        return of(null);
      })
    );
  }

  setupUserSearch(): void {
    this.filteredUsers$ = this.userSearchCtrl.valueChanges.pipe(
      startWith(this.userSearchCtrl.value),
      debounceTime(300),
      distinctUntilChanged(),
      tap(() => this.isLoadingUsers = true),
      switchMap(value => {
        if (typeof value !== 'string' || !value) {
          this.isLoadingUsers = false;
          return of([]);
        }
        return this.userService.searchUsers(value).pipe(
          map(response => response.data), // Extract the array of users
          catchError(err => {
            console.error('Error searching users:', err);
            return of([]);
          }),
          tap(() => this.isLoadingUsers = false)
        );
      })
    );
  }

  loadOrganizations(): void {
    this.organizations$ = this.organizationService.listOrganizations(100, 0).pipe(
      switchMap(res => of(res.data)),
      catchError(err => {
        console.error('Error loading organizations:', err);
        return of([]);
      })
    );
  }

  displayUserFn(user: UserModel): string {
    return user && user.email ? user.email : '';
  }

  onUserSelected(event: any): void {
    this.assignForm.patchValue({ targetUser: event.option.value });
  }

  assignCredits(): void {
    if (this.assignForm.invalid) return;

    const formVal = this.assignForm.value;
    const dto: any = {
      amount: formVal.amount,
      custom_expiration_date: formVal.expirationDate
    };

    if (formVal.targetType === 'user' && formVal.targetUser) {
      dto.target_user_id = formVal.targetUser.id;
    } else if (formVal.targetType === 'org' && formVal.targetOrg) {
      dto.target_org_id = formVal.targetOrg.id;
    } else {
      return;
    }

    if (formVal.targetType === 'user' && !formVal.targetUser?.id) {
      handleErrorSnackbar(this.snackBar, 'Please select a valid user from the list', 'Assign Credits');
      return;
    }

    this.creditsService.assignCredits(dto).subscribe({
      next: () => {
        handleSuccessSnackbar(this.snackBar, 'Credits assigned successfully');
        this.assignForm.reset({ targetType: 'user', amount: 0 });
        this.userSearchCtrl.setValue('');
      },
      error: (err) => {
        console.error('Error assigning credits:', err);
        handleErrorSnackbar(this.snackBar, err, 'Assign Credits');
      }
    });
  }
  
  checkBalance(): void {
    const input = this.checkBalanceCtrl.value;
    if (!input) return;

    this.balanceCheckLoading = true;
    this.balanceResult = null;

    const isEmail = input.includes('@');
    
    if (isEmail) {
      this.userService.searchUsers(input).subscribe({
        next: (users) => {
          const user = users.data.find(u => u.email === input);
          if (user && user.id) {
            this.fetchBalance(user.id, undefined);
          } else {
            handleErrorSnackbar(this.snackBar, 'User not found', 'Check Balance');
            this.balanceCheckLoading = false;
          }
        },
        error: (err) => {
          console.error('Error searching user:', err);
          handleErrorSnackbar(this.snackBar, err, 'Check Balance');
          this.balanceCheckLoading = false;
        }
      });
    } else {
      const orgId = parseInt(input, 10);
      if (!isNaN(orgId)) {
        this.fetchBalance(undefined, orgId);
      } else {
        handleErrorSnackbar(this.snackBar, 'Invalid input', 'Check Balance');
        this.balanceCheckLoading = false;
      }
    }
  }

  private fetchBalance(userId?: number, orgId?: number): void {
    this.creditsService.getBalance(userId, orgId).subscribe({
      next: (res) => {
        this.balanceResult = res.balance;
        this.balanceCheckLoading = false;
      },
      error: (err) => {
        console.error('Error fetching balance:', err);
        handleErrorSnackbar(this.snackBar, err, 'Check Balance');
        this.balanceCheckLoading = false;
      }
    });
  }
  
  loadPriceCatalog(): void {
    this.priceCatalog$ = this.creditsService.getPrices().pipe(
      catchError(err => {
        console.error('Error loading price catalog:', err);
        handleErrorSnackbar(this.snackBar, err, 'Load Price Catalog');
        return of([]);
      })
    );
  }

  editPrice(price: PriceCatalogDto): void {
    const dialogRef = this.dialog.open(PriceCatalogDialogComponent, {
      width: '400px',
      data: { price: price }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        const dto: UpdatePriceCatalogDto = {
          cost: result.cost
        };
        this.creditsService.updatePrice(price.model_id, price.category, dto).subscribe({
          next: () => {
            handleSuccessSnackbar(this.snackBar, 'Price updated successfully');
            this.loadPriceCatalog();
          },
          error: (err) => {
            console.error('Error updating price:', err);
            handleErrorSnackbar(this.snackBar, err, 'Update Price');
          }
        });
      }
    });
  }

  deletePrice(price: PriceCatalogDto): void {
    const dialogRef = this.dialog.open(ConfirmationDialogComponent, {
      data: {
        title: 'Confirm Delete',
        message: `Are you sure you want to delete the price for ${price.model_id}?`
      }
    });

    dialogRef.afterClosed().pipe(filter(result => result)).subscribe(() => {
      this.creditsService.deletePrice(price.model_id, price.category).subscribe({
        next: () => {
          handleSuccessSnackbar(this.snackBar, 'Price deleted successfully');
          this.loadPriceCatalog();
        },
        error: (err) => {
          console.error('Error deleting price:', err);
          handleErrorSnackbar(this.snackBar, err, 'Delete Price');
        }
      });
    });
  }

  addNewPrice(): void {
    const dialogRef = this.dialog.open(PriceCatalogDialogComponent, {
      width: '400px',
      data: { price: undefined }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        const dto: CreatePriceCatalogDto = result;
        this.creditsService.createPrice(dto).subscribe({
          next: () => {
            handleSuccessSnackbar(this.snackBar, 'Price added successfully');
            this.loadPriceCatalog();
          },
          error: (err) => {
            console.error('Error adding price:', err);
            handleErrorSnackbar(this.snackBar, err, 'Add Price');
          }
        });
      }
    });
  }

  ngAfterViewInit(): void {
    this.assignedCreditsData$?.pipe(filter(data => !!data)).subscribe(data => {
      if (data) {
        setTimeout(() => {
          this.renderAssignedCreditsChart(data);
        }, 0);
      }
    });
  }

  loadAssignedCreditsData(): void {
    this.assignedCreditsData$ = this.analyticsService.getAdminAssignedOverTime().pipe(
      catchError(err => {
        console.error('Error loading assigned credits data:', err);
        handleErrorSnackbar(this.snackBar, err, 'Load Assigned Credits Chart');
        return of(null);
      })
    );
  }

  private renderAssignedCreditsChart(data: AssignedCreditsOverTime[]): void {
    if (!this.assignedCreditsChartContainer) return;

    const element = this.assignedCreditsChartContainer.nativeElement;
    d3.select(element).select('svg').remove();

    const margin = { top: 20, right: 30, bottom: 40, left: 60 };
    const width = element.offsetWidth - margin.left - margin.right;
    const height = 300 - margin.top - margin.bottom;

    const svg = d3.select(element).append('svg')
      .attr('width', width + margin.left + margin.right)
      .attr('height', height + margin.top + margin.bottom)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const x = d3.scaleTime()
      .domain(d3.extent(data, d => new Date(d.date)) as [Date, Date])
      .range([0, width]);

    const y = d3.scaleLinear()
      .domain([0, d3.max(data, d => d.total_assigned) || 0])
      .nice()
      .range([height, 0]);

    svg.append('g')
      .attr('transform', `translate(0,${height})`)
      .call(d3.axisBottom(x))
      .selectAll('text')
      .style('fill', '#9ca3af');

    svg.append('g')
      .call(d3.axisLeft(y))
      .selectAll('text')
      .style('fill', '#9ca3af');

    svg.append('text')
        .attr('transform', 'rotate(-90)')
        .attr('y', 0 - margin.left)
        .attr('x', 0 - (height / 2))
        .attr('dy', '1em')
        .style('text-anchor', 'middle')
        .style('fill', '#9ca3af')
        .text('Credits Assigned');

    const line = d3.line<AssignedCreditsOverTime>()
      .x(d => x(new Date(d.date)))
      .y(d => y(d.total_assigned));

    svg.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', '#3b82f6')
      .attr('stroke-width', 2)
      .attr('d', line);

    // Add circles for each data point
    svg.selectAll('.dot')
      .data(data)
      .enter().append('circle')
        .attr('class', 'dot')
        .attr('cx', d => x(new Date(d.date)))
        .attr('cy', d => y(d.total_assigned))
        .attr('r', 4)
        .style('fill', '#3b82f6');

    // Tooltip
    const tooltip = d3.select('body').append('div')
      .attr('class', 'chart-tooltip absolute bg-white text-black border border-gray-300 rounded px-2 py-1 opacity-0 pointer-events-none')
      .style('z-index', '1000');

    const bisectDate = d3.bisector((d: AssignedCreditsOverTime) => new Date(d.date)).left;

    const focus = svg.append('g')
      .append('circle')
        .style('fill', 'none')
        .attr('stroke', '#3b82f6')
        .attr('r', 5)
        .style('opacity', 0);

    svg.append('rect')
      .style('fill', 'none')
      .style('pointer-events', 'all')
      .attr('width', width)
      .attr('height', height)
      .on('mouseover', () => { focus.style('opacity', 1); tooltip.style('opacity', 1); })
      .on('mouseout', () => { focus.style('opacity', 0); tooltip.style('opacity', 0); })
      .on('mousemove', (event) => {
        const mouseX = d3.pointer(event)[0];
        const x0 = x.invert(mouseX);
        const i = bisectDate(data, x0, 1);
        const d0 = data[i - 1];
        const d1 = data[i];
        const d = (d1 && (x0.valueOf() - new Date(d0.date).valueOf() > new Date(d1.date).valueOf() - x0.valueOf())) ? d1 : d0;

        focus.attr('cx', x(new Date(d.date))).attr('cy', y(d.total_assigned));

        tooltip
          .html(`Date: ${d.date}<br>Assigned: ${d.total_assigned}`)
          .style('left', (event.pageX + 15) + 'px')
          .style('top', (event.pageY - 28) + 'px');
      });
  }

  ngOnDestroy(): void {
    d3.select('body').selectAll('.chart-tooltip').remove();
  }
}
