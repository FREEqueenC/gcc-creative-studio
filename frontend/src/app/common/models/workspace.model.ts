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
  can_manage_members: boolean;
  can_edit: boolean;
  can_delete: boolean;
  can_view_workflows: boolean;
  can_manage_workflows: boolean;
  can_view_images: boolean;
  can_generate_images: boolean;
  can_view_videos: boolean;
  can_generate_videos: boolean;
  can_view_audio: boolean;
  can_generate_audio: boolean;
  can_view_vto: boolean;
  can_generate_vto: boolean;
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
  permissions?: WorkspacePermissions;
}
