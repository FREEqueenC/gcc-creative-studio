/**
 * Copyright 2026 Google LLC
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

import {TestBed} from '@angular/core/testing';
import {VideoStateService} from './video-state.service';
import {SettingsService} from './settings.service';

describe('VideoStateService', () => {
  let service: VideoStateService;
  let settingsServiceSpy: jasmine.SpyObj<SettingsService>;

  beforeEach(() => {
    localStorage.clear();
    const spy = jasmine.createSpyObj('SettingsService', ['getShowGeminiOmni']);
    settingsServiceSpy = spy;
  });

  afterEach(() => {
    localStorage.clear();
  });

  function initService() {
    TestBed.configureTestingModule({
      providers: [
        VideoStateService,
        {provide: SettingsService, useValue: settingsServiceSpy},
      ],
    });
    service = TestBed.inject(VideoStateService);
  }

  it('should be created', () => {
    settingsServiceSpy.getShowGeminiOmni.and.returnValue(false);
    initService();
    expect(service).toBeTruthy();
  });

  it('should use default initial state if localStorage is empty (omni disabled)', () => {
    settingsServiceSpy.getShowGeminiOmni.and.returnValue(false);
    initService();
    const state = service.getState();
    expect(state.prompt).toBe('');
    expect(state.aspectRatio).toBe('16:9');
    expect(state.model).toBe('veo-3.1-generate-001');
    expect(state.numberOfMedia).toBe(4);
  });

  it('should use default initial state if localStorage is empty (omni enabled)', () => {
    settingsServiceSpy.getShowGeminiOmni.and.returnValue(true);
    initService();
    const state = service.getState();
    expect(state.prompt).toBe('');
    expect(state.aspectRatio).toBe('16:9');
    expect(state.model).toBe('gemini-omni-generate-preview');
    expect(state.numberOfMedia).toBe(1);
  });

  it('should load initial state from localStorage if present', () => {
    settingsServiceSpy.getShowGeminiOmni.and.returnValue(false);
    const savedState = {
      prompt: 'a cinematic shot of a forest',
      aspectRatio: '9:16',
      model: 'custom-video-model',
    };
    localStorage.setItem('video_state', JSON.stringify(savedState));

    initService();
    const state = service.getState();
    expect(state.prompt).toBe('a cinematic shot of a forest');
    expect(state.aspectRatio).toBe('9:16');
    expect(state.model).toBe('custom-video-model');
  });

  it('should update state and save to localStorage when updateState is called', () => {
    settingsServiceSpy.getShowGeminiOmni.and.returnValue(false);
    initService();

    service.updateState({prompt: 'updated video prompt', durationSeconds: 12});

    const state = service.getState();
    expect(state.prompt).toBe('updated video prompt');
    expect(state.durationSeconds).toBe(12);

    const saved = localStorage.getItem('video_state');
    expect(saved).toBeTruthy();
    if (saved) {
      const parsed = JSON.parse(saved);
      expect(parsed.prompt).toBe('updated video prompt');
      expect(parsed.durationSeconds).toBe(12);
    }
  });

  it('should reset state and remove from localStorage when resetState is called', () => {
    settingsServiceSpy.getShowGeminiOmni.and.returnValue(false);
    initService();

    service.updateState({prompt: 'temporary video prompt'});
    expect(localStorage.getItem('video_state')).toBeTruthy();

    service.resetState();
    expect(service.getState().prompt).toBe('');
    expect(localStorage.getItem('video_state')).toBeNull();
  });

  it('should fallback to default state and not crash if localStorage contains invalid JSON', () => {
    settingsServiceSpy.getShowGeminiOmni.and.returnValue(false);
    localStorage.setItem('video_state', 'invalid { json');
    initService();
    const state = service.getState();
    expect(state.prompt).toBe('');
    expect(state.aspectRatio).toBe('16:9');
  });
});
