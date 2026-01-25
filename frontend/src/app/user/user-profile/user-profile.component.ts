import { Component, OnInit } from '@angular/core';
import { AuthService } from '../../common/services/auth.service';
import { AnalyticsService, UserUsage } from '../../common/services/analytics.service';
import { UserModel } from '../../common/models/user.model';
import { Observable, of } from 'rxjs';
import { switchMap, catchError } from 'rxjs/operators';

@Component({
  selector: 'app-user-profile',
  templateUrl: './user-profile.component.html',
  styleUrls: ['./user-profile.component.scss']
})
export class UserProfileComponent implements OnInit {
  currentUser$: Observable<UserModel | null>;
  userUsage$: Observable<UserUsage | null> | undefined;

  constructor(
    private authService: AuthService,
    private analyticsService: AnalyticsService
  ) {
    this.currentUser$ = this.authService.currentUser$;
  }

  ngOnInit(): void {
    this.userUsage$ = this.currentUser$.pipe(
      switchMap(user => {
        if (user && user.id) {
          return this.analyticsService.getUserUsage(user.id).pipe(
            catchError(err => {
              console.error('Error loading user usage:', err);
              return of(null);
            })
          );
        }
        return of(null);
      })
    );
  }
}
