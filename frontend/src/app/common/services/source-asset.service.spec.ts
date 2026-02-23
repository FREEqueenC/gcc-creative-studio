
import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { SourceAssetService, SourceAssetResponseDto, PaginationResponseDto } from './source-asset.service';
import { environment } from '../../../environments/environment';
import { AssetScopeEnum, AssetTypeEnum } from '../../admin/source-assets-management/source-asset.model';

describe('SourceAssetService', () => {
  let service: SourceAssetService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [SourceAssetService]
    });
    service = TestBed.inject(SourceAssetService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should upload an asset', () => {
    const file = new File([''], 'test.png', { type: 'image/png' });
    const mockResponse: SourceAssetResponseDto = { id: 1, userId: '1', gcsUri: '', originalFilename: '', mimeType: '', aspectRatio: '', fileHash: '', createdAt: '', updatedAt: '', presignedUrl: '' };

    service.uploadAsset(file).subscribe(response => {
      expect(response).toEqual(mockResponse);
    });

    const req = httpMock.expectOne(`${environment.backendURL}/source_assets/upload`);
    expect(req.request.method).toBe('POST');
    req.flush(mockResponse);

    // uploadAsset triggers refreshAssets which triggers loadAssets which triggers search
    const searchReq = httpMock.expectOne(`${environment.backendURL}/source_assets/search`);
    expect(searchReq.request.method).toBe('POST');
    searchReq.flush({ data: [], count: 0, page: 0, pageSize: 0, totalPages: 0 });
  });

  it('should upload an asset with options', () => {
    const file = new File([''], 'test.png', { type: 'image/png' });
    const options = { aspectRatio: '1:1', assetType: AssetTypeEnum.GENERIC_IMAGE, scope: AssetScopeEnum.PRIVATE };
    const mockResponse: SourceAssetResponseDto = { id: 1, userId: '1', gcsUri: '', originalFilename: '', mimeType: '', aspectRatio: '', fileHash: '', createdAt: '', updatedAt: '', presignedUrl: '' };

    service.uploadAsset(file, options).subscribe(response => {
      expect(response).toEqual(mockResponse);
    });

    const req = httpMock.expectOne(`${environment.backendURL}/source_assets/upload`);
    expect(req.request.method).toBe('POST');
    const formData = req.request.body as FormData;
    expect(formData.get('aspectRatio')).toBe('1:1');
    expect(formData.get('assetType')).toBe(AssetTypeEnum.GENERIC_IMAGE);
    expect(formData.get('scope')).toBe(AssetScopeEnum.PRIVATE);
    req.flush(mockResponse);

    // uploadAsset triggers refreshAssets which triggers loadAssets which triggers search
    const searchReq = httpMock.expectOne(`${environment.backendURL}/source_assets/search`);
    expect(searchReq.request.method).toBe('POST');
    searchReq.flush({ data: [], count: 0, page: 0, pageSize: 0, totalPages: 0 });
  });

  it('should fetch assets', () => {
    const mockResponse: PaginationResponseDto<SourceAssetResponseDto> = {
      data: [],
      count: 0,
      page: 0,
      pageSize: 0,
      totalPages: 0
    };

    service.loadAssets();

    const req = httpMock.expectOne(`${environment.backendURL}/source_assets/search`);
    expect(req.request.method).toBe('POST');
    req.flush(mockResponse);

    service.assets.subscribe(assets => {
      expect(assets).toEqual([]);
    });
  });

  it('should delete an asset', () => {
    const assetId = 1;
    service.deleteAsset(assetId).subscribe();

    const req = httpMock.expectOne(`${environment.backendURL}/source_assets/${assetId}`);
    expect(req.request.method).toBe('DELETE');
    req.flush({});
  });

  it('should get an asset', () => {
    const assetId = 1;
    const mockResponse: SourceAssetResponseDto = { id: 1, userId: '1', gcsUri: '', originalFilename: '', mimeType: '', aspectRatio: '', fileHash: '', createdAt: '', updatedAt: '', presignedUrl: '' };

    service.getAsset(assetId).subscribe(response => {
      expect(response).toEqual(mockResponse);
    });

    const req = httpMock.expectOne(`${environment.backendURL}/source_assets/${assetId}`);
    expect(req.request.method).toBe('GET');
    req.flush(mockResponse);
  });

  it('should add an asset to the list', () => {
    const asset: SourceAssetResponseDto = { id: 1, userId: '1', gcsUri: '', originalFilename: '', mimeType: '', aspectRatio: '', fileHash: '', createdAt: '', updatedAt: '', presignedUrl: '' };
    service.addAsset(asset);
    service.assets.subscribe(assets => {
      expect(assets).toEqual([asset]);
    });
  });

  it('should set filters and reload assets', () => {
    const filters = { mimeType: 'image/png' };
    spyOn(service, 'loadAssets');
    service.setFilters(filters);
    expect(service.loadAssets).toHaveBeenCalledWith(true);
  });

  it('should not set filters if they are the same', () => {
    const filters = { mimeType: 'image/png' };
    service.setFilters(filters);
    const req = httpMock.expectOne(`${environment.backendURL}/source_assets/search`);
    req.flush({
      data: [],
      count: 0,
      page: 0,
      pageSize: 0,
      totalPages: 0
    });
    spyOn(service, 'loadAssets');
    service.setFilters(filters);
    expect(service.loadAssets).not.toHaveBeenCalled();
  });

});
