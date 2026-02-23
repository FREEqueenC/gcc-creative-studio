
import { TestBed } from '@angular/core/testing';
import { MediaResolutionService } from './media-resolution.service';
import { GalleryService } from '../../gallery/gallery.service';
import { SourceAssetService } from '../../common/services/source-asset.service';
import { of } from 'rxjs';
import { NodeTypes } from '../workflow.models';
import { STEP_CONFIGS_MAP } from './step-configs.map';

describe('MediaResolutionService', () => {
  let service: MediaResolutionService;
  let galleryService: GalleryService;
  let sourceAssetService: SourceAssetService;

  const mockGalleryService = {
    getMedia: jasmine.createSpy('getMedia').and.returnValue(of({ presignedUrls: ['http://media.url'] }))
  };

  const mockSourceAssetService = {
    getAsset: jasmine.createSpy('getAsset').and.returnValue(of({ presignedUrl: 'http://asset.url' }))
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        MediaResolutionService,
        { provide: GalleryService, useValue: mockGalleryService },
        { provide: SourceAssetService, useValue: mockSourceAssetService }
      ]
    });
    service = TestBed.inject(MediaResolutionService);
    galleryService = TestBed.inject(GalleryService);
    sourceAssetService = TestBed.inject(SourceAssetService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should resolve media urls', () => {
    const stepEntries = [
      {
        step_id: 'step1',
        step_outputs: { edited_image: 1 },
        step_inputs: { input_images: { sourceAssetId: 2 } }
      }
    ];
    const stepTypeMap = new Map<string, NodeTypes | string>([
        ['step1', NodeTypes.EDIT_IMAGE]
    ]);
    const mediaUrlMap = new Map<string, string>();

    service.resolveMediaUrls(stepEntries, stepTypeMap, mediaUrlMap);

    expect(galleryService.getMedia).toHaveBeenCalledWith(1);
    expect(sourceAssetService.getAsset).toHaveBeenCalledWith(2);
    expect(mediaUrlMap.get('media:1')).toBe('http://media.url');
    expect(mediaUrlMap.get('asset:2')).toBe('http://asset.url');
  });

  it('should resolve media urls with references', () => {
    const stepEntries = [
      {
        step_id: 'step1',
        step_outputs: { generated_image: 1 },
        step_inputs: {}
      },
      {
          step_id: 'step2',
          step_inputs: { input_images: { step: 'step1', output: 'generated_image' } },
          step_outputs: {},
      }
    ];
    const stepTypeMap = new Map<string, NodeTypes | string>([
        ['step1', NodeTypes.GENERATE_IMAGE],
        ['step2', NodeTypes.EDIT_IMAGE]
    ]);
    const mediaUrlMap = new Map<string, string>();

    service.resolveMediaUrls(stepEntries, stepTypeMap, mediaUrlMap);

    expect(galleryService.getMedia).toHaveBeenCalledWith(1);
    expect(mediaUrlMap.get('media:1')).toBe('http://media.url');
  });

});
