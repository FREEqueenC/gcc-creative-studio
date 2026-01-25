import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule } from '@angular/forms';
import { MatRadioModule } from '@angular/material/radio';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatTableModule } from '@angular/material/table';
import { MatIconModule } from '@angular/material/icon';
import { MatDialogModule } from '@angular/material/dialog';

import { CreditsAnalyticsComponent } from './credits-analytics.component';
import { PriceCatalogDialogComponent } from './price-catalog-dialog.component';
import { SharedModule } from '../../common/shared.module';

@NgModule({
  declarations: [
    CreditsAnalyticsComponent,
    PriceCatalogDialogComponent
  ],
  imports: [
    CommonModule,
    SharedModule,
    ReactiveFormsModule,
    MatRadioModule,
    MatAutocompleteModule,
    MatDatepickerModule,
    MatNativeDateModule,
    MatTableModule,
    MatIconModule,
    MatDialogModule
  ],
  exports: [
    CreditsAnalyticsComponent
  ]
})
export class CreditsAnalyticsModule { }
