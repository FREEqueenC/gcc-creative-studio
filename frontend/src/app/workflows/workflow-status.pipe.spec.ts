import {WorkflowStatusPipe} from './workflow-status.pipe';

describe('WorkflowStatusPipe', () => {
  let pipe: WorkflowStatusPipe;

  beforeEach(() => {
    pipe = new WorkflowStatusPipe();
  });

  it('create an instance', () => {
    expect(pipe).toBeTruthy();
  });

  it('should transform status to icon', () => {
    expect(pipe.transform('RUNNING', 'icon')).toBe('hourglass_top');
    expect(pipe.transform('ACTIVE', 'icon')).toBe('hourglass_top');
    expect(pipe.transform('COMPLETED', 'icon')).toBe('check_circle');
    expect(pipe.transform('SUCCEEDED', 'icon')).toBe('check_circle');
    expect(pipe.transform('FAILED', 'icon')).toBe('error');
    expect(pipe.transform('PENDING', 'icon')).toBe('schedule');
    expect(pipe.transform('SKIPPED', 'icon')).toBe('skip_next');
    expect(pipe.transform('CANCELLED', 'icon')).toBe('cancel');
  });

  it('should transform status to class', () => {
    expect(pipe.transform('RUNNING', 'class')).toBe(
      '!bg-blue-500/20 !text-blue-300',
    );
    expect(pipe.transform('ACTIVE', 'class')).toBe(
      '!bg-blue-500/20 !text-blue-300',
    );
    expect(pipe.transform('COMPLETED', 'class')).toBe(
      '!bg-green-500/20 !text-green-300',
    );
    expect(pipe.transform('SUCCEEDED', 'class')).toBe(
      '!bg-green-500/20 !text-green-300',
    );
    expect(pipe.transform('FAILED', 'class')).toBe(
      '!bg-red-500/20 !text-red-300',
    );
    expect(pipe.transform('PENDING', 'class')).toBe(
      '!bg-gray-500/20 !text-gray-300',
    );
    expect(pipe.transform('SKIPPED', 'class')).toBe(
      '!bg-amber-500/20 !text-amber-300',
    );
    expect(pipe.transform('CANCELLED', 'class')).toBe(
      '!bg-red-500/20 !text-red-300',
    );
  });

  it('should handle STATE_ prefix', () => {
    expect(pipe.transform('STATE_RUNNING', 'icon')).toBe('hourglass_top');
    expect(pipe.transform('STATE_RUNNING', 'class')).toBe(
      '!bg-blue-500/20 !text-blue-300',
    );
  });

  it('should handle unknown status', () => {
    expect(pipe.transform('UNKNOWN', 'icon')).toBe('help_outline');
    expect(pipe.transform('UNKNOWN', 'class')).toBe(
      '!bg-gray-500/20 !text-gray-300',
    );
  });

  it('should handle null or undefined status', () => {
    expect(pipe.transform(null, 'icon')).toBe('help_outline');
    expect(pipe.transform(undefined, 'icon')).toBe('help_outline');
    expect(pipe.transform(null, 'class')).toBe(
      '!bg-gray-500/20 !text-gray-300',
    );
    expect(pipe.transform(undefined, 'class')).toBe(
      '!bg-gray-500/20 !text-gray-300',
    );
  });
});
