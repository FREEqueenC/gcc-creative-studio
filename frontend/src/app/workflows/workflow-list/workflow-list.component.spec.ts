import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { MatDialog, MatDialogRef } from '@angular/material/dialog';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatSort } from '@angular/material/sort';
import { MatTableDataSource } from '@angular/material/table';
import { Router } from '@angular/router';
import { of, Subject, throwError } from 'rxjs';
import { ConfirmationDialogComponent } from '../../common/components/confirmation-dialog/confirmation-dialog.component';
import { WorkflowListComponent } from './workflow-list.component';
import { WorkflowModel, WorkflowRunStatusEnum } from '../workflow.models';
import { WorkflowService } from '../workflow.service';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { MaterialModule } from '../../common/material.module';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { By } from '@angular/platform-browser';
import { RouterTestingModule } from '@angular/router/testing';
import { DebugElement } from '@angular/core';
import { DatePipe } from '@angular/common';

describe('WorkflowListComponent', () => {
  let component: WorkflowListComponent;
  let fixture: ComponentFixture<WorkflowListComponent>;
  let mockWorkflowService: jasmine.SpyObj<WorkflowService>;
  let mockRouter: jasmine.SpyObj<Router>;
  let mockMatDialog: jasmine.SpyObj<MatDialog>;
  let nativeElement: HTMLElement;
  let debugElement: DebugElement;
  let datePipe: DatePipe;

  const mockWorkflows: WorkflowModel[] = [
    {
      id: '1', name: 'Workflow 1', description: 'Description 1', createdAt: '2023-01-01T12:00:00Z', updatedAt: new Date().toISOString(),
      userId: '',
      steps: []
    },
    {
      id: '2', name: 'Workflow 2', description: 'Description 2', createdAt: '2023-01-02T12:00:00Z', updatedAt: new Date().toISOString(),
      userId: '',
      steps: []
    },
  ];

  beforeEach(async () => {
    mockWorkflowService = jasmine.createSpyObj('WorkflowService', ['setFilter', 'deleteWorkflow'], {
      workflows$: new Subject<WorkflowModel[]>(),
      isLoading$: new Subject<boolean>(),
      errorMessage$: new Subject<string | null>(),
    });
    mockRouter = jasmine.createSpyObj('Router', ['navigate']);
    mockMatDialog = jasmine.createSpyObj('MatDialog', ['open']);

    await TestBed.configureTestingModule({
      declarations: [WorkflowListComponent],
      imports: [
        HttpClientTestingModule,
        MaterialModule,
        NoopAnimationsModule,
        RouterTestingModule.withRoutes([]),
      ],
      providers: [
        { provide: WorkflowService, useValue: mockWorkflowService },
        { provide: Router, useValue: mockRouter },
        { provide: MatDialog, useValue: mockMatDialog },
        DatePipe
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(WorkflowListComponent);
    component = fixture.componentInstance;
    nativeElement = fixture.nativeElement;
    debugElement = fixture.debugElement;
    datePipe = TestBed.inject(DatePipe);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should have correct initial pagination state', () => {
    expect(component.totalWorkflows).toBe(0);
    expect(component.limit).toBe(10);
    expect(component.currentPageIndex).toBe(0);
  });

  it('should initialize and subscribe to workflow service observables', () => {
    (mockWorkflowService.workflows$ as Subject<WorkflowModel[]>).next(mockWorkflows);
    (mockWorkflowService.isLoading$ as Subject<boolean>).next(true);
    (mockWorkflowService.errorMessage$ as Subject<string | null>).next('Error');

    expect(component.dataSource.data).toEqual(mockWorkflows);
    expect(component.isLoading).toBe(true);
    expect(component.errorMessage).toBe('Error');
  });

  it('should set the sort on ngAfterViewInit', () => {
    const sort = {} as MatSort;
    component.sort = sort;
    component.ngAfterViewInit();
    expect(component.dataSource.sort).toBe(sort);
  });

  it('should handle page events', () => {
    const pageEvent: PageEvent = { pageIndex: 1, pageSize: 10, length: 100 };
    spyOn(component, 'handlePageEvent').and.callThrough();
    component.handlePageEvent(pageEvent);
    expect(component.handlePageEvent).toHaveBeenCalledWith(pageEvent);
  });

  it('should call setFilter on filter change', fakeAsync(() => {
    const filterValue = 'test filter';
    component.applyFilter({ target: { value: filterValue } } as any);
    tick(500);
    expect(mockWorkflowService.setFilter).toHaveBeenCalledWith(filterValue);
  }));

  it('should navigate to new workflow page', () => {
    component.createNewWorkflow();
    expect(mockRouter.navigate).toHaveBeenCalledWith(['/workflows/new']);
  });

  describe('deleteWorkflow', () => {
    const workflow: WorkflowModel = {
      id: '1', name: 'Test Workflow', description: '', createdAt: '', updatedAt: '',
      userId: '',
      steps: []
    };
    const event = new MouseEvent('click');
    spyOn(event, 'stopPropagation');


    it('should open confirmation dialog', () => {
      mockMatDialog.open.and.returnValue({ afterClosed: () => of(false) } as MatDialogRef<any>);
      component.deleteWorkflow(workflow, event);
      expect(mockMatDialog.open).toHaveBeenCalledWith(ConfirmationDialogComponent, {
        width: '350px',
        data: {
          title: 'Confirm Deletion',
          message: `Are you sure you want to delete the workflow "${workflow.name}"? This action cannot be undone.`,
        },
      });
      expect(event.stopPropagation).toHaveBeenCalled();
    });

    it('should call deleteWorkflow on confirmation', () => {
      mockMatDialog.open.and.returnValue({ afterClosed: () => of(true) } as MatDialogRef<any>);
      mockWorkflowService.deleteWorkflow.and.returnValue(of({}));
      component.deleteWorkflow(workflow, event);
      expect(mockWorkflowService.deleteWorkflow).toHaveBeenCalledWith(workflow.id);
    });

    it('should set error message on deletion failure', () => {
      mockMatDialog.open.and.returnValue({ afterClosed: () => of(true) } as MatDialogRef<any>);
      const errorResponse = 'Failed to delete';
      mockWorkflowService.deleteWorkflow.and.returnValue(throwError(() => new Error(errorResponse)));
      component.deleteWorkflow(workflow, event);
      expect(component.errorMessage).toBe('Failed to delete workflow. Please try again.');
    });
  });

  describe('UI functions', () => {
    it('getWorkflowRunStatusChipClass should return correct class', () => {
      expect(component.getWorkflowRunStatusChipClass(WorkflowRunStatusEnum.RUNNING)).toContain('blue');
      expect(component.getWorkflowRunStatusChipClass(WorkflowRunStatusEnum.COMPLETED)).toContain('green');
      expect(component.getWorkflowRunStatusChipClass(WorkflowRunStatusEnum.SCHEDULED)).toContain('amber');
      expect(component.getWorkflowRunStatusChipClass(WorkflowRunStatusEnum.FAILED)).toContain('red');
      expect(component.getWorkflowRunStatusChipClass(WorkflowRunStatusEnum.CANCELED)).toContain('red');
      expect(component.getWorkflowRunStatusChipClass('other' as WorkflowRunStatusEnum)).toContain('gray');
    });

    it('getWorkflowRunStatusIcon should return correct icon', () => {
      expect(component.getWorkflowRunStatusIcon(WorkflowRunStatusEnum.RUNNING)).toBe('directions_run');
      expect(component.getWorkflowRunStatusIcon(WorkflowRunStatusEnum.COMPLETED)).toBe('check_circle');
      expect(component.getWorkflowRunStatusIcon(WorkflowRunStatusEnum.SCHEDULED)).toBe('schedule');
      expect(component.getWorkflowRunStatusIcon(WorkflowRunStatusEnum.FAILED)).toBe('cancel');
      expect(component.getWorkflowRunStatusIcon(WorkflowRunStatusEnum.CANCELED)).toBe('cancel');
      expect(component.getWorkflowRunStatusIcon('other' as WorkflowRunStatusEnum)).toBe('help_outline');
    });
  });

  describe('Template', () => {
    it('should have a create button with correct icon', () => {
      const button = debugElement.query(By.css('button[mat-raised-button]'));
      const icon = button.query(By.css('mat-icon'));
      expect(icon.nativeElement.textContent.trim()).toBe('add');
    });

    it('should have a filter input with correct icon', () => {
      const formField = debugElement.query(By.css('mat-form-field'));
      const icon = formField.query(By.css('mat-icon[matSuffix]'));
      expect(icon.nativeElement.textContent.trim()).toBe('search');
    });
    
    it('should display loading spinner when isLoading is true and hide when false', () => {
      component.isLoading = true;
      fixture.detectChanges();
      let spinner = nativeElement.querySelector('mat-progress-spinner');
      expect(spinner).toBeTruthy();

      component.isLoading = false;
      fixture.detectChanges();
      spinner = nativeElement.querySelector('mat-progress-spinner');
      expect(spinner).toBeFalsy();
    });

    it('should display error message when errorMessage is set and hide when null', () => {
      component.errorMessage = 'Test Error';
      fixture.detectChanges();
      let errorDiv = nativeElement.querySelector('.error-message');
      expect(errorDiv).toBeTruthy();
      expect(errorDiv?.textContent).toContain('Test Error');

      component.errorMessage = null;
      fixture.detectChanges();
      errorDiv = nativeElement.querySelector('.error-message');
      expect(errorDiv).toBeFalsy();
    });

    it('should display table headers with sort capabilities', () => {
        fixture.detectChanges();
        const headerCells = nativeElement.querySelectorAll('th[mat-header-cell]');
        const headerTexts = Array.from(headerCells).map(cell => cell.textContent?.trim());
        expect(headerTexts).toEqual(['Name', 'Description', 'Created At', 'Updated At', 'Actions']);
        headerCells.forEach(cell => {
          if(!cell.classList.contains('!text-right')) { //The actions column has no sort
            expect(cell.hasAttribute('mat-sort-header')).toBeTrue();
          }
        });
    });

    it('should correctly bind data to the paginator', () => {
      component.totalWorkflows = 100;
      component.limit = 10;
      fixture.detectChanges();
      const paginator = debugElement.query(By.css('mat-paginator'));
      expect(paginator).toBeTruthy();
      expect(paginator.componentInstance.length).toBe(100);
      expect(paginator.componentInstance.pageSize).toBe(10);
      expect(paginator.componentInstance.pageSizeOptions).toEqual([10, 25, 100]);
    });

    describe('with data', () => {
        beforeEach(() => {
            component.dataSource.data = mockWorkflows;
            fixture.detectChanges();
        });

        it('should render a row for each workflow', () => {
            const rows = nativeElement.querySelectorAll('tr[mat-row]');
            expect(rows.length).toBe(mockWorkflows.length);
        });

        it('should display the correct data in each cell', () => {
            const row = nativeElement.querySelector('tr[mat-row]')!;
            const cells = row.querySelectorAll('td[mat-cell]');
            
            expect(cells[0].textContent?.trim()).toBe('Workflow 1');
            expect(cells[1].textContent?.trim()).toBe('Description 1');
            const descriptionCell = debugElement.queryAll(By.css('td[mat-cell]'))[1];
            expect(descriptionCell.attributes['ng-reflect-tooltip']).toBe('Description 1');
            expect(cells[2].textContent?.trim()).toBe(datePipe.transform(mockWorkflows[0].createdAt, 'longDate') || '');
            expect(cells[3].textContent?.trim()).toBe(component.formatTimeAgo(mockWorkflows[0].updatedAt));
        });

        it('should have correct routerLinks for action buttons', () => {
            const actionButtons = debugElement.queryAll(By.css('td[mat-cell] button[mat-icon-button]'));
            
            const historyButton = actionButtons[0];
            const editButton = actionButtons[1];

            expect(historyButton.attributes['ng-reflect-router-link']).toBe('/workflows,1,executions');
            expect(editButton.attributes['ng-reflect-router-link']).toBe('/workflows/edit,1');
        });

        it('should not show the no data row', () => {
            const noDataRow = nativeElement.querySelector('tr.mat-no-data-row');
            expect(noDataRow).toBeFalsy();
        });
    });

    describe('without data', () => {
        beforeEach(() => {
            component.dataSource.data = [];
            fixture.detectChanges();
        });

        it('should show the no data row', () => {
            const noDataRow = nativeElement.querySelector('tr.mat-row');
            expect(noDataRow).toBeTruthy();
            const cell = noDataRow!.querySelector('td.mat-cell');
            expect(cell).toBeTruthy();
            expect(cell!.textContent).toContain('No workflows found.');
            expect(cell!.getAttribute('colspan')).toBe(String(component.displayedColumns.length));
        });

        it('should not render any data rows', () => {
            const dataRows = nativeElement.querySelectorAll('tr[mat-row]:not(.mat-no-data-row)');
            expect(dataRows.length).toBe(0);
        });
    });
  });

  it('should unsubscribe on destroy', () => {
    const destroy$ = (component as any).destroy$;
    spyOn(destroy$, 'next');
    spyOn(destroy$, 'complete');
    const subscriptions = (component as any).subscriptions;
    spyOn(subscriptions, 'unsubscribe');

    component.ngOnDestroy();

    expect(destroy$.next).toHaveBeenCalled();
    expect(destroy$.complete).toHaveBeenCalled();
    expect(subscriptions.unsubscribe).toHaveBeenCalled();
  });
});