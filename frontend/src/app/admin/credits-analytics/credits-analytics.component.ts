import { Component, OnInit } from '@angular/core';
import { AnalyticsService, TokenUsage, TokenBudgets, ActiveRoles } from '../../common/services/analytics.service';
import { AuthService } from '../../common/services/auth.service';
import { Observable, forkJoin, of, Subject } from 'rxjs';
import { catchError, debounceTime, distinctUntilChanged, switchMap, tap, filter } from 'rxjs/operators';
import { FormControl, FormGroup, Validators } from '@angular/forms';
import { UserService } from '../../common/services/user.service';
import { OrganizationService } from '../../services/organization/organization.service';
import { CreditsService, PriceCatalogDto, CreatePriceCatalogDto, UpdatePriceCatalogDto } from '../../services/credits/credits.service';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatDialog } from '@angular/material/dialog';
import { UserModel } from '../../common/models/user.model';
import { Organization } from '../../common/models/organization.model';
import { PriceCatalogDialogComponent, PriceCatalogDialogData } from './price-catalog-dialog.component';
import { ConfirmationDialogComponent } from '../../common/components/confirmation-dialog/confirmation-dialog.component';
@Component({
  selector: 'app-credits-analytics',
  templateUrl: './credits-analytics.component.html',
  styleUrls: ['./credits-analytics.component.scss']
})
export class CreditsAnalyticsComponent implements OnInit {
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
    this.loadGeneralAnalytics();
    this.setupUserSearch();
    this.loadOrganizations();
    this.loadPriceCatalog();
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
      debounceTime(300),
      distinctUntilChanged(),
      tap(() => this.isLoadingUsers = true),
      switchMap(value => {
        if (typeof value !== 'string' || !value) {
          this.isLoadingUsers = false;
          return of([]);
        }
        // Assuming listUsers supports filtering by email/name
        // If not, we might need a specific search endpoint or filter client-side
        return this.userService.searchUsers(value).pipe(
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
    // Load all organizations for the dropdown (paginated, but fetching first page/all for now)
    // Ideally we should have an autocomplete for orgs too if there are many
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
      return; // Should be handled by validators
    }

    this.creditsService.assignCredits(dto).subscribe({
      next: () => {
        this.snackBar.open('Credits assigned successfully', 'Close', { duration: 3000 });
        this.assignForm.reset({ targetType: 'user', amount: 0 });
        this.userSearchCtrl.setValue('');
      },
      error: (err) => {
        console.error('Error assigning credits:', err);
        this.snackBar.open('Failed to assign credits', 'Close', { duration: 3000 });
      }
    });
  }
  
  checkBalance(): void {
    const input = this.checkBalanceCtrl.value;
    if (!input) return;

    this.balanceCheckLoading = true;
    this.balanceResult = null;

    // Determine if input is email or org ID (heuristic)
    const isEmail = input.includes('@');
    
    if (isEmail) {
      this.userService.searchUsers(input).subscribe({
        next: (users) => {
          const user = users.find(u => u.email === input);
          if (user && user.id) {
            this.fetchBalance(user.id, undefined);
          } else {
            this.snackBar.open('User not found', 'Close', { duration: 3000 });
            this.balanceCheckLoading = false;
          }
        },
        error: (err) => {
          console.error('Error searching user:', err);
          this.snackBar.open('Error searching user', 'Close', { duration: 3000 });
          this.balanceCheckLoading = false;
        }
      });
    } else {
      // Assume Org ID
      const orgId = parseInt(input, 10);
      if (!isNaN(orgId)) {
        this.fetchBalance(undefined, orgId);
      } else {
        this.snackBar.open('Invalid input', 'Close', { duration: 3000 });
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
        this.snackBar.open('Failed to fetch balance', 'Close', { duration: 3000 });
        this.balanceCheckLoading = false;
      }
    });
  }
  
  loadPriceCatalog(): void {
    this.priceCatalog$ = this.creditsService.getPrices().pipe(
      catchError(err => {
        console.error('Error loading price catalog:', err);
        this.snackBar.open('Failed to load price catalog', 'Close', { duration: 3000 });
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
          category: result.category,
          cost: result.cost
        };
        this.creditsService.updatePrice(price.model_id, dto).subscribe({
          next: () => {
            this.snackBar.open('Price updated successfully', 'Close', { duration: 3000 });
            this.loadPriceCatalog();
          },
          error: (err) => {
            console.error('Error updating price:', err);
            this.snackBar.open(err.error?.detail || 'Failed to update price', 'Close', { duration: 3000 });
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
      this.creditsService.deletePrice(price.model_id).subscribe({
        next: () => {
          this.snackBar.open('Price deleted successfully', 'Close', { duration: 3000 });
          this.loadPriceCatalog();
        },
        error: (err) => {
          console.error('Error deleting price:', err);
          this.snackBar.open(err.error?.detail || 'Failed to delete price', 'Close', { duration: 3000 });
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
            this.snackBar.open('Price added successfully', 'Close', { duration: 3000 });
            this.loadPriceCatalog();
          },
          error: (err) => {
            console.error('Error adding price:', err);
            this.snackBar.open(err.error?.detail || 'Failed to add price', 'Close', { duration: 3000 });
          }
        });
      }
    });
  }
}
