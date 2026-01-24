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

import {WorkspaceMember} from './workspace-member.model';

export enum WorkspaceScope {
  PUBLIC = 'public',
  PRIVATE = 'private',
}

export interface WorkspacePermissions {
  // --- Workspace Member Management ---
  canAssignWsRoles: boolean;
  canInviteWsMembers: boolean;
  canAddWsMembers: boolean;
  canEditWsMembers: boolean;
  canRemoveWsMembers: boolean;

  // --- Workflows Module (Granular) ---
  canViewWsWorkflows: boolean;
  canExecuteWsWorkflows: boolean;
  canEditWsWorkflows: boolean;

  // --- Brand Guidelines Module (Granular) ---
  canViewWsBrandGuidelines: boolean;
  canEditWsBrandGuidelines: boolean;

  // --- GenAI Features (Standard) ---
  canViewImages: boolean;
  canGenerateImages: boolean;
  canViewVideos: boolean;
  canGenerateVideos: boolean;
  canViewAudio: boolean;
  canGenerateAudio: boolean;
  canViewVto: boolean;
  canGenerateVto: boolean;
}

export interface Workspace {
  id: number;
  name: string;
  ownerId: number; // Updated to number to match backend
  scope: WorkspaceScope;
  members: WorkspaceMember[];
  memberIds: string[];
  organizationId?: number;
  organizationName?: string;
  organizationLogo?: string;
  permissions?: WorkspacePermissions;
  myWsRole?: string;
}
