
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ExecutionDetailsModalComponent } from './execution-details-modal.component';
import { MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { WorkflowService } from '../../workflow.service';
import { GalleryService } from '../../../gallery/gallery.service';
import { MediaResolutionService } from '../../shared/media-resolution.service';
import { of } from 'rxjs';
import { NodeTypes } from '../../workflow.models';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { MaterialModule } from '../../../common/material.module';

import { WorkflowStatusPipe } from '../../workflow-status.pipe';

describe('ExecutionDetailsModalComponent', () => {
  let component: ExecutionDetailsModalComponent;
  let fixture: ComponentFixture<ExecutionDetailsModalComponent>;
  let workflowService: any;
  let mockMediaResolutionService: any;

  const mockDialogRef = {
    close: jasmine.createSpy('close')
  };

  beforeEach(async () => {
    workflowService = {
      getExecutionDetails: jasmine.createSpy('getExecutionDetails').and.callFake(() => of({
        workflow_definition: {
          steps: [
            { stepId: 'step1', type: NodeTypes.GENERATE_IMAGE },
            { stepId: 'step2', type: NodeTypes.USER_INPUT }
          ]
        },
        step_entries: [
          { step_id: 'step1', step_outputs: { image: 1 } },
          { step_id: 'step2', step_outputs: {} }
        ]
      }))
    };

    mockMediaResolutionService = {
      resolveMediaUrls: jasmine.createSpy('resolveMediaUrls')
    };

    await TestBed.configureTestingModule({
      declarations: [ExecutionDetailsModalComponent],
      imports: [
        NoopAnimationsModule,
        MaterialModule,
        WorkflowStatusPipe
      ],
      providers: [
        { provide: MatDialogRef, useValue: mockDialogRef },
        { provide: MAT_DIALOG_DATA, useValue: { workflowId: '1', executionId: '1' } },
        { provide: WorkflowService, useValue: workflowService },
        { provide: GalleryService, useValue: {} },
        { provide: MediaResolutionService, useValue: mockMediaResolutionService }
      ]
    }).compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(ExecutionDetailsModalComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should load details on init', () => {
    expect(workflowService.getExecutionDetails).toHaveBeenCalledWith('1', '1');
    expect(component.details).toBeTruthy();
    expect(component.workflow).toBeTruthy();
    expect(component.visibleStepEntries.length).toBe(1);
    expect(mockMediaResolutionService.resolveMediaUrls).toHaveBeenCalled();
  });

  it('should toggle step expansion', () => {
    component.toggleStep('step1');
    expect(component.expandedSteps.has('step1')).toBe(true);
    component.toggleStep('step1');
    expect(component.expandedSteps.has('step1')).toBe(false);
  });

  it('should check if object has data', () => {
    expect(component.hasData({ a: 1 })).toBe(true);
    expect(component.hasData({})).toBe(false);
    expect(component.hasData(null)).toBe(false);
  });

  it('should get step type', () => {
    expect(component.getStepType('step1')).toBe(NodeTypes.GENERATE_IMAGE);
  });

  it('should check if output is an image', () => {
    expect(component.isImageOutput('step1')).toBe(true);
    component.workflow!.steps[0].type = NodeTypes.GENERATE_TEXT;
    expect(component.isImageOutput('step1')).toBe(false);
  });
});
