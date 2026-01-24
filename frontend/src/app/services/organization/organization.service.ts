import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Organization } from '../../common/models/organization.model';
import { HttpParams } from '@angular/common/http';
import { PaginatedResponse } from '../../common/models/pagination.model';

@Injectable({
  providedIn: 'root'
})
export class OrganizationService {
  private apiUrl = `${environment.backendURL}/organizations`;

  constructor(private http: HttpClient) {}

  listOrganizations(
    limit: number = 100,
    offset: number = 0,
    name?: string
  ): Observable<PaginatedResponse<Organization>> {
    let params = new HttpParams()
      .set('limit', limit.toString())
      .set('offset', offset.toString());

    if (name) {
      params = params.set('name', name);
    }

    return this.http.get<PaginatedResponse<Organization>>(this.apiUrl, { params });
  }

  getOrganization(id: number): Observable<Organization> {
    return this.http.get<Organization>(`${this.apiUrl}/${id}`);
  }
}
