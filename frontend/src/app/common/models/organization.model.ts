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

export interface OrganizationPermissions {
  // --- Organization Member Management ---
  canAccessAdminPanel: boolean;
  canAssignOrgRoles: boolean;
  canInviteOrgMembers: boolean;
  canAddOrgMembers: boolean;
  canEditOrgMembers: boolean;
  canRemoveOrgMembers: boolean;

  // --- Organization Brand Guidelines Management ---
  canEditOrgBrandGuidelines: boolean;
  canEditOrganization: boolean;
  canViewOrgBrandGuidelines: boolean;

  // --- Custom Dynamic Permission ---
  canViewAllOrgWorkspaces: boolean;
}

export interface Organization {
  id: number;
  name: string;
  description?: string;
  logo?: string;
  domain?: string;
  role?: string;
  permissions?: OrganizationPermissions;
  createdAt?: string;
  updatedAt?: string;
}
