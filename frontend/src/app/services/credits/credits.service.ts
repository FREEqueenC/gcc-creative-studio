import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface AssignCreditsDto {
  target_user_id?: number;
  target_org_id?: number;
  amount: number;
  custom_expiration_date?: Date;
}

@Injectable({
  providedIn: 'root'
})
export class CreditsService {
  private apiUrl = `${environment.backendURL}/credits`;

  constructor(private http: HttpClient) {}

  assignCredits(dto: AssignCreditsDto): Observable<any> {
    return this.http.post(`${this.apiUrl}/assign`, dto);
  }

  getBalance(userId?: number, orgId?: number): Observable<{ balance: number }> {
    let params = new HttpParams();
    if (userId) params = params.set('user_id', userId.toString());
    if (orgId) params = params.set('org_id', orgId.toString());
    
    return this.http.get<{ balance: number }>(`${this.apiUrl}/balance`, { params });
  }

  // Price Catalog Methods
  getPrices(): Observable<PriceCatalogDto[]> {
    return this.http.get<PriceCatalogDto[]>(`${this.apiUrl}/prices`);
  }

  createPrice(dto: CreatePriceCatalogDto): Observable<PriceCatalogDto> {
    return this.http.post<PriceCatalogDto>(`${this.apiUrl}/prices`, dto);
  }

  updatePrice(modelId: string, category: string, dto: UpdatePriceCatalogDto): Observable<PriceCatalogDto> {
    return this.http.put<PriceCatalogDto>(`${this.apiUrl}/prices/${modelId}?category=${category}`, dto);
  }

  deletePrice(modelId: string, category: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/prices/${modelId}?category=${category}`);
  }

  // Admin Dashboard Methods
  getAdminOverviewStats(): Observable<AdminOverviewStats> {
    return this.http.get<AdminOverviewStats>(`${this.apiUrl}/admin/overview-stats`);
  }

  getAdminUsageOverTime(): Observable<AdminUsageOverTime[]> {
    return this.http.get<AdminUsageOverTime[]>(`${this.apiUrl}/admin/usage-over-time`);
  }

  getAdminOrganizationBudgets(): Observable<AdminOrganizationBudget[]> {
    return this.http.get<AdminOrganizationBudget[]>(`${this.apiUrl}/admin/organization-budgets`);
  }
}

// Interfaces for Price Catalog
export interface PriceCatalogDto {
  model_id: string;
  category: string;
  cost: number;
  created_at: Date;
  updated_at: Date;
}

export interface CreatePriceCatalogDto {
  model_id: string;
  category: string;
  cost: number;
}

export interface UpdatePriceCatalogDto {
  cost?: number;
}

// Interfaces for Admin Dashboard
export interface AdminOverviewStats {
  totalUsers: number;
  totalOrganizations: number;
  imagesGenerated: number;
  videosGenerated: number;
  audiosGenerated: number;
}

export interface AdminUsageOverTime {
  date: string;
  [key: string]: number | string; // Category: spent
}

export interface AdminOrganizationBudget {
  orgName: string;
  balance: number;
  budget: number;
}
