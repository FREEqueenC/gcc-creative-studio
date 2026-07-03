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

  it('should omit referenceVideo, referenceAudio, and referenceImages when saving state to localStorage', () => {
    settingsServiceSpy.getShowGeminiOmni.and.returnValue(false);
    initService();

    service.updateState({
      prompt: 'video with references',
      referenceImages: [{id: 'img1', url: 'http://example.com/img.png'} as any],
      referenceVideo: {id: 'vid1'} as any,
      referenceAudio: {id: 'aud1'} as any,
    });

    const state = service.getState();
    expect(state.referenceImages.length).toBe(1);
    expect(state.referenceVideo).toBeTruthy();
    expect(state.referenceAudio).toBeTruthy();

    const saved = localStorage.getItem('video_state');
    expect(saved).toBeTruthy();
    if (saved) {
      const parsed = JSON.parse(saved);
      expect(parsed.prompt).toBe('video with references');
      expect(parsed.referenceImages).toBeUndefined();
      expect(parsed.referenceVideo).toBeUndefined();
      expect(parsed.referenceAudio).toBeUndefined();
    }
  });

  it('should not crash if localStorage.getItem throws an error during initialization', () => {
    settingsServiceSpy.getShowGeminiOmni.and.returnValue(false);
    spyOn(localStorage, 'getItem').and.throwError('SecurityError');
    const consoleSpy = spyOn(console, 'error');
    initService();
    expect(service.getState().prompt).toBe('');
    expect(consoleSpy).toHaveBeenCalledWith(
      'Failed to parse saved video state from localStorage',
      jasmine.any(Error),
    );
  });

  it('should not crash if localStorage.setItem throws an error during updateState', () => {
    settingsServiceSpy.getShowGeminiOmni.and.returnValue(false);
    initService();
    spyOn(localStorage, 'setItem').and.throwError('QuotaExceededError');
    const consoleSpy = spyOn(console, 'error');
    expect(() => {
      service.updateState({prompt: 'quota error prompt'});
    }).not.toThrow();
    expect(service.getState().prompt).toBe('quota error prompt');
    expect(consoleSpy).toHaveBeenCalledWith(
      'Failed to save video state to localStorage',
      jasmine.any(Error),
    );
  });

  it('should not crash if localStorage.removeItem throws an error during resetState', () => {
    settingsServiceSpy.getShowGeminiOmni.and.returnValue(false);
    initService();
    spyOn(localStorage, 'removeItem').and.throwError('SecurityError');
    const consoleSpy = spyOn(console, 'error');
    expect(() => {
      service.resetState();
    }).not.toThrow();
    expect(service.getState().prompt).toBe('');
    expect(consoleSpy).toHaveBeenCalledWith(
      'Failed to remove video state from localStorage',
      jasmine.any(Error),
    );
  });

  it('should fallback to default video model if saved state contains Gemini Omni but Gemini Omni is disabled', () => {
    settingsServiceSpy.getShowGeminiOmni.and.returnValue(false);
    const savedState = {
      prompt: 'a cinematic shot',
      model: 'gemini-omni-generate-preview',
      numberOfMedia: 1,
    };
    localStorage.setItem('video_state', JSON.stringify(savedState));
    initService();
    const state = service.getState();
    expect(state.prompt).toBe('a cinematic shot');
    expect(state.model).toBe('veo-3.1-generate-001');
    expect(state.numberOfMedia).toBe(4);
  });
});
