import { Component, OnInit } from '@angular/core';
import { AnalyticsService, TokenUsage, TokenBudgets, ActiveRoles } from '../../common/services/analytics.service';
import { AuthService } from '../../common/services/auth.service';
import { Observable, forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

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

  constructor(
    private analyticsService: AnalyticsService,
    private authService: AuthService
  ) {
    this.isSuperAdmin = this.authService.isUserAdmin() ?? false;
  }

  ngOnInit(): void {
    this.loadGeneralAnalytics();
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
}
