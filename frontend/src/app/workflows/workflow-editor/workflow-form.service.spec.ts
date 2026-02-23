import {TestBed} from '@angular/core/testing';
import {
  FormBuilder,
  ReactiveFormsModule,
  FormGroup,
  FormArray,
} from '@angular/forms';
import {WorkflowFormService} from './workflow-form.service';
import {NodeTypes, StepStatusEnum, WorkflowModel} from '../workflow.models';

describe('WorkflowFormService', () => {
  let service: WorkflowFormService;
  let formBuilder: FormBuilder;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [ReactiveFormsModule],
      providers: [WorkflowFormService, FormBuilder],
    });
    service = TestBed.inject(WorkflowFormService);
    formBuilder = TestBed.inject(FormBuilder);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  describe('initForm', () => {
    it('should initialize a new form without data', () => {
      const form = service.initForm();
      expect(form).toBeInstanceOf(FormGroup);
      expect(form.get('name')?.value).toBe('Untitled Workflow');
      expect(form.get('description')?.value).toBe('');
      const outputDefinitions = form.get(
        'userInput.settings.definitions',
      ) as FormArray;
      expect(outputDefinitions.length).toBe(2);
      expect(outputDefinitions.at(0).get('name')?.value).toBe(
        'User Text Input',
      );
      expect(outputDefinitions.at(1).get('name')?.value).toBe(
        'User Image Input',
      );
    });

    it('should initialize a form with data', () => {
      const mockData: WorkflowModel = {
        id: 'wf-1',
        name: 'Test Workflow',
        description: 'Test Description',
        userId: 'user-1',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        steps: [
          {
            stepId: NodeTypes.USER_INPUT,
            type: NodeTypes.USER_INPUT,
            status: StepStatusEnum.IDLE,
            inputs: {},
            outputs: {
              User_Text_Input: {type: 'text'},
            },
            settings: {
              definitions: [{id: '1', name: 'User Text Input', type: 'text'}],
            },
          },
          {
            stepId: 'generate-text_1',
            type: 'generate-text',
            status: StepStatusEnum.IDLE,
            inputs: {},
            outputs: {},
            settings: {},
          },
        ],
      };

      const form = service.initForm(mockData);
      expect(form.get('id')?.value).toBe('wf-1');
      expect(form.get('name')?.value).toBe('Test Workflow');
      expect(form.get('description')?.value).toBe('Test Description');
      const outputDefinitions = form.get(
        'userInput.settings.definitions',
      ) as FormArray;
      expect(outputDefinitions.length).toBe(1);
      expect(outputDefinitions.at(0).get('name')?.value).toBe(
        'User Text Input',
      );
      const steps = form.get('steps') as FormArray;
      expect(steps.length).toBe(1);
      expect(steps.at(0).get('type')?.value).toBe('generate-text');
    });
  });

  describe('step manipulation', () => {
    beforeEach(() => {
      service.initForm();
    });

    it('should add a step', () => {
      service.addStep('generate-text');
      const steps = service.stepsArray;
      expect(steps.length).toBe(1);
      expect(steps.at(0).get('type')?.value).toBe('generate-text');
    });

    it('should delete a step', () => {
      service.addStep('generate-text');
      service.deleteStep(0);
      const steps = service.stepsArray;
      expect(steps.length).toBe(0);
    });

    it('should move a step', () => {
      service.addStep('generate-text');
      service.addStep('generate-image');
      const steps = service.stepsArray;
      expect(steps.at(0).get('type')?.value).toBe('generate-text');
      service.moveStep(0, 1);
      expect(steps.at(0).get('type')?.value).toBe('generate-image');
    });
  });

  describe('output manipulation', () => {
    beforeEach(() => {
      service.initForm();
    });

    it('should add an output definition', () => {
      service.addOutputDefinition('New Output', 'text');
      const definitions = service.outputDefinitionsArray;
      expect(definitions.length).toBe(3);
      expect(definitions.at(2).get('name')?.value).toBe('New Output');
    });

    it('should remove an output definition', () => {
      service.removeOutputDefinition(0);
      const definitions = service.outputDefinitionsArray;
      expect(definitions.length).toBe(1);
    });
  });
});
