import { Component, Inject, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { PriceCatalogDto, CreatePriceCatalogDto, UpdatePriceCatalogDto } from '../../services/credits/credits.service';

export interface PriceCatalogDialogData {
  price?: PriceCatalogDto;
}

@Component({
  selector: 'app-price-catalog-dialog',
  templateUrl: './price-catalog-dialog.component.html',
  styleUrls: ['./price-catalog-dialog.component.scss']
})
export class PriceCatalogDialogComponent implements OnInit {
  priceForm: FormGroup;
  isEditMode: boolean;

  constructor(
    private fb: FormBuilder,
    public dialogRef: MatDialogRef<PriceCatalogDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: PriceCatalogDialogData
  ) {
    this.isEditMode = !!this.data.price;
    this.priceForm = this.fb.group({
      model_id: [{ value: this.data.price?.model_id || '', disabled: this.isEditMode }, Validators.required],
      category: [this.data.price?.category || '', Validators.required],
      cost: [this.data.price?.cost || 0, [Validators.required, Validators.min(0)]]
    });
  }

  ngOnInit(): void {}

  onCancel(): void {
    this.dialogRef.close();
  }

  onSave(): void {
    if (this.priceForm.valid) {
      const formValue = this.priceForm.getRawValue();
      this.dialogRef.close(formValue);
    }
  }
}
