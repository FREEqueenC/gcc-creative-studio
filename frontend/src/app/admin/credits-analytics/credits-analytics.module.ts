import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { CreditsAnalyticsRoutingModule } from './credits-analytics-routing.module';
import { CreditsAnalyticsComponent } from './credits-analytics.component';
import { SharedModule } from '../../common/shared.module';

@NgModule({
  declarations: [
    CreditsAnalyticsComponent
  ],
  imports: [
    CommonModule,
    CreditsAnalyticsRoutingModule,
    SharedModule
  ],
  exports: [
    CreditsAnalyticsComponent
  ]
})
export class CreditsAnalyticsModule { }
