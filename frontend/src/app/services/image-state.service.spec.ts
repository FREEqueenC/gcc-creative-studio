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
import {ImageStateService, ImageState} from './image-state.service';

describe('ImageStateService', () => {
  let service: ImageStateService;

  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('should be created', () => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(ImageStateService);
    expect(service).toBeTruthy();
  });

  it('should use default initial state if localStorage is empty', () => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(ImageStateService);
    const state = service.getState();
    expect(state.prompt).toBe('');
    expect(state.aspectRatio).toBe('1:1');
    expect(state.model).toBe('gemini-3.1-flash-image');
  });

  it('should load initial state from localStorage if present', () => {
    const savedState: Partial<ImageState> = {
      prompt: 'a futuristic city',
      aspectRatio: '16:9',
      model: 'custom-model',
    };
    localStorage.setItem('image_state', JSON.stringify(savedState));

    TestBed.configureTestingModule({});
    service = TestBed.inject(ImageStateService);
    const state = service.getState();
    expect(state.prompt).toBe('a futuristic city');
    expect(state.aspectRatio).toBe('16:9');
    expect(state.model).toBe('custom-model');
  });

  it('should update state and save to localStorage when updateState is called', () => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(ImageStateService);
    
    service.updateState({prompt: 'new prompt', aspectRatio: '4:3'});
    
    const state = service.getState();
    expect(state.prompt).toBe('new prompt');
    expect(state.aspectRatio).toBe('4:3');

    const saved = localStorage.getItem('image_state');
    expect(saved).toBeTruthy();
    if (saved) {
      const parsed = JSON.parse(saved);
      expect(parsed.prompt).toBe('new prompt');
      expect(parsed.aspectRatio).toBe('4:3');
    }
  });

  it('should reset state and remove from localStorage when resetState is called', () => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(ImageStateService);
    
    service.updateState({prompt: 'temporary prompt'});
    expect(localStorage.getItem('image_state')).toBeTruthy();

    service.resetState();
    expect(service.getState().prompt).toBe('');
    expect(localStorage.getItem('image_state')).toBeNull();
  });
});
