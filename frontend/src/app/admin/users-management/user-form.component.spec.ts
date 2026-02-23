
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { UserFormComponent } from './user-form.component';
import { MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { MaterialModule } from '../../common/material.module';

describe('UserFormComponent', () => {
  let component: UserFormComponent;
  let fixture: ComponentFixture<UserFormComponent>;
  let dialogRef: MatDialogRef<UserFormComponent>;

  const mockDialogRef = {
    close: jasmine.createSpy('close')
  };

  const mockDialogData = {
    user: {
      id: '1',
      email: 'test@example.com',
      roles: ['user']
    },
    isEditMode: true
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [UserFormComponent],
      imports: [
        ReactiveFormsModule,
        NoopAnimationsModule,
        MaterialModule
      ],
      providers: [
        FormBuilder,
        { provide: MatDialogRef, useValue: mockDialogRef },
        { provide: MAT_DIALOG_DATA, useValue: mockDialogData }
      ]
    }).compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(UserFormComponent);
    component = fixture.componentInstance;
    dialogRef = TestBed.inject(MatDialogRef);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should initialize the form with user data', () => {
    expect(component.userForm.get('email')?.value).toEqual(mockDialogData.user.email);
    expect(component.userForm.get('roles')?.value).toEqual(mockDialogData.user.roles);
    expect(component.isEditMode).toBe(true);
  });

  it('should close the dialog on cancel', () => {
    component.onCancel();
    expect(dialogRef.close).toHaveBeenCalled();
  });

  it('should close the dialog with form data on submit when form is valid', () => {
    component.onSubmit();
    expect(dialogRef.close).toHaveBeenCalledWith(component.userForm.getRawValue());
  });

  it('should mark all fields as touched on submit when form is invalid', () => {
    component.userForm.get('roles')?.setValue([]);
    component.onSubmit();
    expect(component.userForm.touched).toBe(true);
    expect(dialogRef.close).not.toHaveBeenCalledWith(component.userForm.getRawValue());
  });
});
