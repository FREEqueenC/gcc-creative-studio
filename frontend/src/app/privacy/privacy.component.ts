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

import {Component, OnInit} from '@angular/core';
import {ActivatedRoute, Router} from '@angular/router';

@Component({
  selector: 'app-privacy',
  templateUrl: './privacy.component.html',
  styleUrl: './privacy.component.scss',
})
export class PrivacyComponent implements OnInit {
  activeTab: 'privacy' | 'terms' = 'privacy';

  constructor(
    private route: ActivatedRoute,
    private router: Router
  ) {}

  ngOnInit(): void {
    // Determine active tab based on path
    const urlPath = this.router.url;
    if (urlPath.includes('terms-of-service')) {
      this.activeTab = 'terms';
    } else {
      this.activeTab = 'privacy';
    }
  }

  setTab(tab: 'privacy' | 'terms'): void {
    this.activeTab = tab;
    // Update path silently without reload
    const targetPath = tab === 'terms' ? '/terms-of-service' : '/privacy';
    void this.router.navigateByUrl(targetPath, {replaceUrl: true});
  }

  goBack(): void {
    void this.router.navigate(['/']);
  }
}
