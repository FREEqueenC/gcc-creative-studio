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

import {ComponentFixture, TestBed} from '@angular/core/testing';
import {WorkbenchComponent} from './workbench.component';
import {MatDialog, MatDialogModule} from '@angular/material/dialog';
import {NoopAnimationsModule} from '@angular/platform-browser/animations';
import {of} from 'rxjs';
import {ImageSelectorComponent} from '../common/components/image-selector/image-selector.component';
import {MediaItem, JobStatus} from '../common/models/media-item.model';
import {MatIconModule} from '@angular/material/icon';
import {MatIconTestingModule} from '@angular/material/icon/testing';
import {FormsModule} from '@angular/forms';
import {MatSliderModule} from '@angular/material/slider';

describe('WorkbenchComponent', () => {
  let component: WorkbenchComponent;
  let fixture: ComponentFixture<WorkbenchComponent>;
  let dialog: MatDialog;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [WorkbenchComponent],
      imports: [
        NoopAnimationsModule,
        MatDialogModule,
        MatIconModule,
        MatIconTestingModule,
        FormsModule,
        MatSliderModule,
      ],
      providers: [
        {
          provide: MatDialog,
          useValue: {
            open: () => ({
              afterClosed: () => of(null),
            }),
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(WorkbenchComponent);
    component = fixture.componentInstance;
    dialog = TestBed.inject(MatDialog);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  describe('File Handling', () => {
    it('should add a video asset when a video file is selected', () => {
      const file = new File([''], 'video.mp4', {type: 'video/mp4'});
      const event = {target: {files: [file]}} as unknown as Event;

      spyOn(URL, 'createObjectURL').and.returnValue(
        'blob:http://localhost/123',
      );
      spyOn(component, 'extractVideoMetadata' as any);

      component.onFileSelected(event);

      expect(component.assets().length).toBe(1);
      expect(component.assets()[0].type).toBe('video');
      expect(component.extractVideoMetadata).toHaveBeenCalled();
    });

    it('should add an audio asset when an audio file is selected', () => {
      const file = new File([''], 'audio.mp3', {type: 'audio/mpeg'});
      const event = {target: {files: [file]}} as unknown as Event;

      spyOn(URL, 'createObjectURL').and.returnValue(
        'blob:http://localhost/456',
      );
      spyOn(component, 'extractAudioMetadata' as any);

      component.onFileSelected(event);

      expect(component.assets().length).toBe(1);
      expect(component.assets()[0].type).toBe('audio');
      expect(component.extractAudioMetadata).toHaveBeenCalled();
    });

    it('should not add an asset if the file type is not supported', () => {
      const file = new File([''], 'text.txt', {type: 'text/plain'});
      const event = {target: {files: [file]}} as unknown as Event;

      component.onFileSelected(event);

      expect(component.assets().length).toBe(0);
    });
  });

  describe('Cloud Media Selection', () => {
    it('should open the media selector dialog', () => {
      spyOn(dialog, 'open').and.returnValue({
        afterClosed: () => of(null),
      } as any);

      component.openMediaSelector();

      expect(dialog.open).toHaveBeenCalledWith(
        ImageSelectorComponent,
        jasmine.any(Object),
      );
    });

    it('should process a gallery item result from the dialog', () => {
      const mediaItem: MediaItem = {
        id: 1,
        prompt: 'test',
        presignedUrls: ['http://test.com/video.mp4'],
        presignedThumbnailUrls: ['http://test.com/thumb.jpg'],
        mimeType: 'video/mp4',
        createdAt: '',
        gcsUris: [],
        status: JobStatus.COMPLETED,
        updatedAt: '',
      };
      const result = {mediaItem, selectedIndex: 0};
      spyOn(dialog, 'open').and.returnValue({
        afterClosed: () => of(result),
      } as any);
      spyOn(component as any, 'extractVideoMetadataFromUrl');

      component.openMediaSelector();

      expect(component.assets().length).toBe(1);
      expect(component.assets()[0].name).toBe('test');
      expect((component as any).extractVideoMetadataFromUrl).toHaveBeenCalled();
    });
  });

  // Add more tests here

  describe('Timeline and Asset Management', () => {
    let videoAsset: any;

    let audioAsset: any;

    beforeEach(() => {
      videoAsset = {
        id: 'video1',
        name: 'video.mp4',
        type: 'video',
        duration: 10,
        safeUrl: '',
      };

      audioAsset = {
        id: 'audio1',
        name: 'audio.mp3',
        type: 'audio',
        duration: 5,
        safeUrl: '',
      };

      component.assets.set([videoAsset, audioAsset]);
    });

    it('should delete an asset and its clips from the timeline', () => {
      component.addToTimeline(videoAsset);

      expect(component.timelineClips().length).toBe(2);

      const event = new MouseEvent('click');

      spyOn(event, 'stopPropagation');

      component.deleteAsset(videoAsset, event);

      expect(component.assets().length).toBe(1);

      expect(component.timelineClips().length).toBe(0);

      expect(event.stopPropagation).toHaveBeenCalled();
    });

    it('should clear thumbnail on error', () => {
      videoAsset.thumbnail = 'some-url';
      component.assets.set([videoAsset]);
      component.onThumbnailError(videoAsset);
      expect(component.assets()[0].thumbnail).toBeUndefined();
    });

    it('should add a video to the timeline', () => {
      component.addToTimeline(videoAsset);

      expect(component.timelineClips().length).toBe(2);

      expect(component.timelineClips()[0].trackIndex).toBe(0);

      expect(component.timelineClips()[1].trackIndex).toBe(1);
    });

    it('should add an audio to the timeline', () => {
      component.addToTimeline(audioAsset);

      expect(component.timelineClips().length).toBe(1);

      expect(component.timelineClips()[0].trackIndex).toBe(1);
    });

    it('should calculate total duration correctly', () => {
      component.addToTimeline(videoAsset); // duration 10
      component.addToTimeline(audioAsset); // duration 5
      expect(component.totalDuration()).toBe(10);
    });

    it('should return asset name', () => {
      expect(component.getAssetName('video1')).toBe('video.mp4');
      expect(component.getAssetName('unknown')).toBe('Clip');
    });

    it('should check if asset is video', () => {
      expect(component.isAssetVideo('video1')).toBeTrue();
      expect(component.isAssetVideo('audio1')).toBeFalse();
    });

    it('should delete a selected clip from the timeline', () => {
      component.addToTimeline(videoAsset);
      const clipId = component.timelineClips()[0].id;
      component.selectedClipId.set(clipId);

      component.deleteSelectedClip();

      expect(
        component.timelineClips().find(c => c.id === clipId),
      ).toBeUndefined();
      expect(component.selectedClipId()).toBeNull();
    });
  });

  describe('Splitting Clips', () => {
    let videoAsset: any;

    beforeEach(() => {
      videoAsset = {
        id: 'video1',
        name: 'video.mp4',
        type: 'video',
        duration: 10,
        safeUrl: '',
      };
      component.assets.set([videoAsset]);
      component.addToTimeline(videoAsset);
    });

    it('should return true for canSplit if a clip is selected and the playhead is within its bounds', () => {
      const clipId = component.timelineClips()[0].id;
      component.selectedClipId.set(clipId);
      component.currentTime.set(5);

      expect(component.canSplit()).toBeTrue();
    });

    it('should split a selected clip', () => {
      const originalClip = component.timelineClips()[0];
      component.selectedClipId.set(originalClip.id);
      component.currentTime.set(4); // Split at 4 seconds

      component.splitSelectedClip();

      const clips = component.timelineClips();
      expect(clips.length).toBe(3); // Original video clip, its audio, and the new split video clip

      const clip1 = clips.find(c => c.id === originalClip.id);
      const clip2 = clips.find(
        c => c.id !== originalClip.id && c.trackIndex === 0,
      );

      expect(clip1?.duration).toBe(4);
      expect(clip2).toBeDefined();
      expect(clip2!.duration).toBe(6);
      expect(clip2!.offset).toBe(4);
      expect(component.selectedClipId()).toBe(clip2!.id);
    });
  });

  describe('UI Interactions', () => {
    it('should activate a tool button if none is active', () => {
      component.toggleToolButton('gallery');
      expect(component.activeToolButton()).toBe('gallery');
    });

    it('should deactivate a tool button if it is already active', () => {
      component.activeToolButton.set('gallery');
      component.toggleToolButton('gallery');
      expect(component.activeToolButton()).toBeNull();
    });

    it('should filter assets when active tab changes', () => {
      const videoAsset = {id: 'v1', type: 'video'} as any;
      const audioAsset = {id: 'a1', type: 'audio'} as any;
      component.assets.set([videoAsset, audioAsset]);

      component.activeTab.set('audio');
      fixture.detectChanges();

      expect(component.filteredAssets().length).toBe(1);
      expect(component.filteredAssets()[0].id).toBe('a1');
    });
  });

  describe('Drag and Drop', () => {
    let videoAsset: any;

    beforeEach(() => {
      videoAsset = {
        id: 'video1',
        name: 'video.mp4',
        type: 'video',
        duration: 10,
        safeUrl: '',
      };
      component.assets.set([videoAsset]);
      component.addToTimeline(videoAsset);
    });

    it('should start dragging a clip', () => {
      const clip = component.timelineClips()[0];
      const event = {
        clientX: 100,
        stopPropagation: () => {},
        preventDefault: () => {},
      } as any;
      component.startDrag(event, clip);
      expect(component.dragState).toEqual({
        active: true,
        clipId: clip.id,
        startX: 100,
        initialStartTime: clip.startTime,
      });
    });

    it('should move a clip on drag', () => {
      const clip = component.timelineClips()[0];
      component.dragState = {
        active: true,
        clipId: clip.id,
        startX: 100,
        initialStartTime: 0,
      };
      const event = {clientX: 250} as MouseEvent; // 150px change => 10s
      component.onDragMove(event);
      expect(component.timelineClips()[0].startTime).toBe(10);
    });

    it('should resolve overlaps on drag end', () => {
      const clip = component.timelineClips()[0];
      component.dragState = {
        active: true,
        clipId: clip.id,
        startX: 100,
        initialStartTime: 5,
      };
      component.onDragEnd();
      expect(component.dragState).toBeNull();
      // In this case, since it's the only video clip, it should snap back to the start.
      expect(component.timelineClips()[0].startTime).toBe(0);
    });
  });
});

