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

import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ReactiveFormsModule, Validators } from '@angular/forms';
import { MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { MatSelectModule } from '@angular/material/select';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { MediaTemplateFormComponent } from './media-template-form.component';
import { MaterialModule } from '../../../common/material.module';
import { of } from 'rxjs';
import { MimeTypeEnum } from '../../../fun-templates/media-template.model';
import { MatChipInputEvent } from '@angular/material/chips';

import { MatChipsModule } from '@angular/material/chips';

describe('MediaTemplateFormComponent', () => {
  let component: MediaTemplateFormComponent;
  let fixture: ComponentFixture<MediaTemplateFormComponent>;
  let dialogRef: MatDialogRef<MediaTemplateFormComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [MediaTemplateFormComponent],
      imports: [
        ReactiveFormsModule,
        HttpClientTestingModule,
        MaterialModule,
        NoopAnimationsModule,
        MatSelectModule,
        MatChipsModule,
      ],
      providers: [
        {
          provide: MatDialogRef,
          useValue: {
            close: () => {},
            afterClosed: () => of(true),
          },
        },
        { provide: MAT_DIALOG_DATA, useValue: { template: {} } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(MediaTemplateFormComponent);
    component = fixture.componentInstance;
    dialogRef = TestBed.inject(MatDialogRef);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should initialize the form on ngOnInit', () => {
    component.ngOnInit();
    expect(component.form).toBeDefined();
    expect(component.form.controls['name'].validator).toBe(
      Validators.required,
    );
    expect(component.form.controls['description'].validator).toBe(
      Validators.required,
    );
    expect(component.form.controls['mimeType'].validator).toBe(
      Validators.required,
    );
  });

  it('should update filtered models when mimeType changes to IMAGE', () => {
    component.form.get('mimeType')?.setValue(MimeTypeEnum.IMAGE);
    component.updateFilteredModels();
    expect(component.filteredGenerationModels).toEqual(component.imageModels);
  });

  it('should update filtered models when mimeType changes to VIDEO', () => {
    component.form.get('mimeType')?.setValue(MimeTypeEnum.VIDEO);
    component.updateFilteredModels();
    expect(component.filteredGenerationModels).toEqual(component.videoModels);
  });

  it('should reset filtered models for other mimeTypes', () => {
    component.form.get('mimeType')?.setValue(null);
    component.updateFilteredModels();
    expect(component.filteredGenerationModels).toEqual([]);
  });

  it('should add a tag to the form', () => {
    const event = { value: 'new tag', chipInput: { clear: () => {} } };
    component.addTag(event as MatChipInputEvent);
    expect(component.tags.length).toBe(1);
    expect(component.tags.at(0).value).toBe('new tag');
  });

  it('should remove a tag from the form', () => {
    component.addTag({
      value: 'tag 1',
      chipInput: { clear: () => {} },
    } as MatChipInputEvent);
    component.removeTag(0);
    expect(component.tags.length).toBe(0);
  });

  it('should add a gcsUri to the form', () => {
    component.addGcsUri();
    expect(component.gcsUris.length).toBe(1);
    expect(component.gcsUris.at(0).validator).toBe(Validators.required);
  });

  it('should remove a gcsUri from the form', () => {
    component.addGcsUri();
    component.removeGcsUri(0);
    expect(component.gcsUris.length).toBe(0);
  });

  it('should add a thumbnailUri to the form', () => {
    component.addThumbnailUri();
    expect(component.thumbnailUris.length).toBe(1);
  });

  it('should remove a thumbnailUri from the form', () => {
    component.addThumbnailUri();
    component.removeThumbnailUri(0);
    expect(component.thumbnailUris.length).toBe(0);
  });

  it('should close the dialog on onCancel', () => {
    spyOn(dialogRef, 'close');
    component.onCancel();
    expect(dialogRef.close).toHaveBeenCalled();
  });

  it('should close the dialog with form value on onSave if form is valid', () => {
    spyOn(dialogRef, 'close');
    component.form.get('name')?.setValue('test');
    component.form.get('description')?.setValue('test description');
    component.form.get('mimeType')?.setValue(MimeTypeEnum.IMAGE);
    component.onSave();
    expect(dialogRef.close).toHaveBeenCalledWith(component.form.value);
  });

  it('should not close the dialog on onSave if form is invalid', () => {
    spyOn(dialogRef, 'close');
    component.onSave();
    expect(dialogRef.close).not.toHaveBeenCalled();
  });

  it('should initialize the form with template data', () => {
    const template = {
      id: '1',
      name: 'Test Template',
      description: 'Test Description',
      mimeType: MimeTypeEnum.IMAGE,
      industry: 'Test Industry',
      brand: 'Test Brand',
      tags: ['tag1', 'tag2'],
      gcsUris: ['uri1', 'uri2'],
      thumbnailUris: ['thumb1', 'thumb2'],
      generationParameters: {
        prompt: 'Test Prompt',
        model: 'image-model',
        aspectRatio: '1:1',
        style: 'digital-art',
        lighting: 'daylight',
        colorAndTone: 'vibrant',
        composition: 'close-up',
        negativePrompt: 'Test Negative Prompt',
      },
    };
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      declarations: [MediaTemplateFormComponent],
      imports: [
        ReactiveFormsModule,
        HttpClientTestingModule,
        MaterialModule,
        NoopAnimationsModule,
        MatSelectModule,
        MatChipsModule,
      ],
      providers: [
        {
          provide: MatDialogRef,
          useValue: {
            close: () => {},
            afterClosed: () => of(true),
          },
        },
        { provide: MAT_DIALOG_DATA, useValue: { template: template } },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(MediaTemplateFormComponent);
    component = fixture.componentInstance;
    dialogRef = TestBed.inject(MatDialogRef);
    fixture.detectChanges();

    expect(component.form.value).toEqual(template);
  });

  it('should unsubscribe on ngOnDestroy', () => {
    spyOn((component as any).mimeTypeSubscription, 'unsubscribe');
    component.ngOnDestroy();
    expect((component as any).mimeTypeSubscription.unsubscribe).toHaveBeenCalled();
  });
});
