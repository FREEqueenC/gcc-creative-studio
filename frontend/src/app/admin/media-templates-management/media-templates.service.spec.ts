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

import { TestBed } from '@angular/core/testing';
import {
  HttpClientTestingModule,
  HttpTestingController,
} from '@angular/common/http/testing';
import { MediaTemplatesService } from './media-templates.service';
import {
  MediaTemplate,
  MimeTypeEnum,
  IndustryEnum,
} from '../../fun-templates/media-template.model';
import { PaginatedResponse } from '../../common/models/paginated-response.model';
import { environment } from '../../../environments/environment';

describe('MediaTemplatesService', () => {
  let service: MediaTemplatesService;
  let httpMock: HttpTestingController;
  const apiUrl = `${environment.backendURL}/media-templates`;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [MediaTemplatesService],
    });
    service = TestBed.inject(MediaTemplatesService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  describe('getMediaTemplates', () => {
    it('should return a paginated response of media templates', () => {
      const mockResponse: PaginatedResponse<MediaTemplate> = {
        data: [
          {
            id: 1,
            name: 'Test Template',
            description: 'Test Description',
            mimeType: MimeTypeEnum.IMAGE,
            industry: IndustryEnum.OTHER,
            tags: [],
            presignedUrls: [],
            generationParameters: {},
          },
        ],
        count: 1,
        page: 1,
        pageSize: 10,
        totalPages: 1,
      };

      service.getMediaTemplates().subscribe((response) => {
        expect(response).toEqual(mockResponse);
      });

      const req = httpMock.expectOne(apiUrl);
      expect(req.request.method).toBe('GET');
      req.flush(mockResponse);
    });
  });

  describe('createMediaTemplate', () => {
    it('should create a media template', () => {
      const newTemplate: MediaTemplate = {
        id: 1,
        name: 'New Template',
        description: 'New Description',
        mimeType: MimeTypeEnum.IMAGE,
        industry: IndustryEnum.OTHER,
        tags: [],
        presignedUrls: [],
        generationParameters: {},
      };

      service.createMediaTemplate(newTemplate).subscribe((response) => {
        expect(response).toEqual(newTemplate);
      });

      const req = httpMock.expectOne(apiUrl);
      expect(req.request.method).toBe('POST');
      req.flush(newTemplate);
    });
  });

  describe('updateMediaTemplate', () => {
    it('should update a media template', () => {
      const updatedTemplate: MediaTemplate = {
        id: 1,
        name: 'Updated Template',
        description: 'Updated Description',
        mimeType: MimeTypeEnum.IMAGE,
        industry: IndustryEnum.OTHER,
        tags: [],
        presignedUrls: [],
        generationParameters: {},
      };
      const payload = {
        name: 'Updated Template',
        description: 'Updated Description',
      };

      service
        .updateMediaTemplate(1, payload as Omit<MediaTemplate, 'id' | 'mimeType'>)
        .subscribe((response) => {
          expect(response).toEqual(updatedTemplate);
        });

      const req = httpMock.expectOne(`${apiUrl}/1`);
      expect(req.request.method).toBe('PUT');
      req.flush(updatedTemplate);
    });
  });

  describe('deleteMediaTemplate', () => {
    it('should delete a media template', () => {
      service.deleteMediaTemplate(1).subscribe((response) => {
        expect(response).toBeNull();
      });

      const req = httpMock.expectOne(`${apiUrl}/1`);
      expect(req.request.method).toBe('DELETE');
      req.flush(null);
    });
  });

  describe('handleError', () => {
    it('should handle client-side errors', () => {
      const errorEvent = new ErrorEvent('error', { message: 'network error' });
      service.getMediaTemplates().subscribe({
        error: (err) => {
          expect(err.message).toContain('Error: network error');
        },
      });

      const req = httpMock.expectOne(apiUrl);
      req.error(errorEvent);
    });

    it('should handle backend errors with detail', () => {
      const errorResponse = {
        status: 422,
        statusText: 'Unprocessable Entity',
        error: { detail: [{ loc: ['body', 'name'], msg: 'field required' }] },
      };

      service.getMediaTemplates().subscribe({
        error: (err) => {
          expect(err.message).toContain('Error Code: 422');
          expect(err.message).toContain(
            'Details: [{"loc":["body","name"],"msg":"field required"}]'
          );
        },
      });

      const req = httpMock.expectOne(apiUrl);
      req.flush(errorResponse.error, {
        status: errorResponse.status,
        statusText: errorResponse.statusText,
      });
    });

    it('should handle backend errors without detail', () => {
      const errorResponse = {
        status: 500,
        statusText: 'Internal Server Error',
        error: { message: 'Something went wrong' },
      };

      service.getMediaTemplates().subscribe({
        error: (err) => {
          expect(err.message).toContain('Error Code: 500');
          expect(err.message).toContain(
            'Backend Error: {"message":"Something went wrong"}'
          );
        },
      });

      const req = httpMock.expectOne(apiUrl);
      req.flush(errorResponse.error, {
        status: errorResponse.status,
        statusText: errorResponse.statusText,
      });
    });
  });
});
