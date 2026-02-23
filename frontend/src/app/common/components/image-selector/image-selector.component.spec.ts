
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ImageSelectorComponent } from './image-selector.component';
import { MatDialog, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { SourceAssetService } from '../../services/source-asset.service';
import { of } from 'rxjs';
import { AssetTypeEnum } from '../../../admin/source-assets-management/source-asset.model';

import { MaterialModule } from '../../material.module';

import { MatTabsModule } from '@angular/material/tabs';
import { NO_ERRORS_SCHEMA } from '@angular/core';
import { provideNoopAnimations } from '@angular/platform-browser/animations';

describe('ImageSelectorComponent', () => {
  let component: ImageSelectorComponent;
  let fixture: ComponentFixture<ImageSelectorComponent>;
  let dialog: MatDialog;
  let dialogRef: MatDialogRef<ImageSelectorComponent>;
  let sourceAssetService: SourceAssetService;

  const mockDialogRef = {
    close: jasmine.createSpy('close')
  };

  const mockDialog = {
    open: jasmine.createSpy('open').and.returnValue({ afterClosed: () => of({ id: '1' }) })
  };

  const mockSourceAssetService = {
    uploadAsset: jasmine.createSpy('uploadAsset').and.returnValue(of({ id: '1' }))
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ImageSelectorComponent],
      imports: [
        MaterialModule,
        MatTabsModule
      ],
      providers: [
        { provide: MatDialogRef, useValue: mockDialogRef },
        { provide: MatDialog, useValue: mockDialog },
        { provide: SourceAssetService, useValue: mockSourceAssetService },
        { provide: MAT_DIALOG_DATA, useValue: { assetType: AssetTypeEnum.GENERIC_IMAGE, mimeType: 'image/*' } },
        provideNoopAnimations()
      ],
      schemas: [NO_ERRORS_SCHEMA]
    }).compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(ImageSelectorComponent);
    component = fixture.componentInstance;
    dialog = TestBed.inject(MatDialog);
    dialogRef = TestBed.inject(MatDialogRef);
    sourceAssetService = TestBed.inject(SourceAssetService);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should open image cropper for image files', () => {
    const file = new File([''], 'test.png', { type: 'image/png' });
    component.handleFileSelect(file);
    expect(dialog.open).toHaveBeenCalled();
  });

  it('should upload video files directly', () => {
    const file = new File([''], 'test.mp4', { type: 'video/mp4' });
    component.handleFileSelect(file);
    expect(sourceAssetService.uploadAsset).toHaveBeenCalledWith(file);
    expect(dialogRef.close).toHaveBeenCalledWith({ id: '1' });
  });

  it('should upload audio files directly', () => {
    const file = new File([''], 'test.mp3', { type: 'audio/mpeg' });
    component.handleFileSelect(file);
    expect(sourceAssetService.uploadAsset).toHaveBeenCalledWith(file);
    expect(dialogRef.close).toHaveBeenCalledWith({ id: '1' });
  });

  it('should handle file selection from event', () => {
    const file = new File([''], 'test.png', { type: 'image/png' });
    const event = { currentTarget: { files: [file] } } as any;
    spyOn(component, 'handleFileSelect');
    component.onFileSelected(event);
    expect(component.handleFileSelect).toHaveBeenCalledWith(file);
  });

  it('should handle file drop', () => {
    const file = new File([''], 'test.png', { type: 'image/png' });
    const event = { dataTransfer: { files: [file] }, preventDefault: () => {}, stopPropagation: () => {} } as any;
    spyOn(component, 'handleFileSelect');
    component.onDrop(event);
    expect(component.handleFileSelect).toHaveBeenCalledWith(file);
  });

  it('should close dialog on media item selection', () => {
    const selection = { mediaItem: { id: '1' }, selectedIndex: 0 };
    component.onMediaItemSelected(selection as any);
    expect(dialogRef.close).toHaveBeenCalledWith(selection);
  });

  it('should close dialog on asset selection', () => {
    const asset = { id: '1' };
    component.onAssetSelected(asset as any);
    expect(dialogRef.close).toHaveBeenCalledWith(asset);
  });

  it('should return correct accept types', () => {
    expect(component.getAcceptTypes()).toBe('image/*');
    component.data.mimeType = 'video/*';
    expect(component.getAcceptTypes()).toContain('video/*');
    component.data.mimeType = 'audio/*';
    expect(component.getAcceptTypes()).toContain('audio/*');
    component.data.mimeType = null;
    expect(component.getAcceptTypes()).toContain('image/*,video/*,audio/*');
  });
});
