/**
 * Copyright 2026 Google LLC
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

import {Component, NgZone, Inject, PLATFORM_ID} from '@angular/core';
import {GoogleAuthProvider} from '@angular/fire/auth';
import {Router} from '@angular/router';
import {AuthService} from './../common/services/auth.service';
import {UserModel} from './../common/models/user.model';
import {MatSnackBar} from '@angular/material/snack-bar';
import {handleErrorSnackbar} from '../utils/handleMessageSnackbar';
import {environment} from '../../environments/environment';
import {isPlatformBrowser} from '@angular/common';

const HOME_ROUTE = '/';

declare let google: any;
declare let grecaptcha: any;

interface LooseObject {
  [key: string]: any;
}

@Component({
  selector: 'app-login',
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.scss'],
})
export class LoginComponent {
  private readonly provider: GoogleAuthProvider = new GoogleAuthProvider();

  loader = false;
  invalidLogin = false;
  errorMessage = '';
  isBrowser: boolean;

  constructor(
    private authService: AuthService,
    private router: Router,
    public ngZone: NgZone,
    private _snackBar: MatSnackBar,
    @Inject(PLATFORM_ID) platformId: Object,
  ) {
    this.isBrowser = isPlatformBrowser(platformId);
    this.provider.setCustomParameters({
      prompt: 'select_account',
    });
  }

  ngOnInit(): void {
    if (this.isBrowser) {
      google.accounts.id.initialize({
        client_id: environment.GOOGLE_CLIENT_ID,
        callback: this.handleCredentialResponse.bind(this),
        auto_select: false,
        cancel_on_tap_outside: true,
      });
      google.accounts.id.renderButton(
        document.getElementById('google-signin-button'),
        {theme: 'outline', size: 'large', width: '300'},
      );
      google.accounts.id.renderButton(
        document.getElementById('google-signin-button-desktop'),
        {theme: 'outline', size: 'large', width: '300'},
      );
    }
  }

  handleCredentialResponse(response: any) {
    this.loader = true;
    this.authService
      .handleGoogleCredentialResponse(response.credential)
      .subscribe({
        next: () => {
          this.ngZone.run(() => {
            this.loader = false;
            void this.router.navigate([HOME_ROUTE]);
          });
        },
        error: (error: any) => {
          this.handleLoginError(error);
        },
      });
  }

  private handleLoginError(error: any, postErrorAction?: () => void) {
    this.loader = false;
    handleErrorSnackbar(this._snackBar, error, 'Login Error');
    if (postErrorAction) {
      postErrorAction();
    }
  }

  redirect(user: UserModel) {
    if (this.isBrowser) {
      localStorage.setItem('USER_DETAILS', JSON.stringify(user));
    }
    this.loader = false;
    void this.router.navigate([HOME_ROUTE]);
  }
}
