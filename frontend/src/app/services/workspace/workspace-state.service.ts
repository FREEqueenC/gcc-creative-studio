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

import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { Workspace } from '../../common/models/workspace.model';

@Injectable({
  providedIn: 'root',
})
export class WorkspaceStateService {
  private readonly activeWorkspaceIdSubject = new BehaviorSubject<
    number | null
  >(null);
  public readonly activeWorkspaceId$: Observable<number | null> =
    this.activeWorkspaceIdSubject.asObservable();

  private readonly activeWorkspaceSubject = new BehaviorSubject<
    Workspace | null
  >(null);
  public readonly activeWorkspace$: Observable<Workspace | null> =
    this.activeWorkspaceSubject.asObservable();

  setActiveWorkspaceId(workspaceId: number | null) {
    this.activeWorkspaceIdSubject.next(workspaceId);
  }

  setActiveWorkspace(workspace: Workspace | null) {
    this.activeWorkspaceSubject.next(workspace);
    if (workspace) {
      this.setActiveWorkspaceId(workspace.id);
    } else {
      this.setActiveWorkspaceId(null);
    }
  }

  getActiveWorkspaceId(): number | null {
    return this.activeWorkspaceIdSubject.getValue();
  }

  getActiveWorkspace(): Workspace | null {
    return this.activeWorkspaceSubject.getValue();
  }
}
