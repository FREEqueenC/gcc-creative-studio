import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CreditsAnalyticsComponent } from './credits-analytics.component';

describe('CreditsAnalyticsComponent', () => {
  let component: CreditsAnalyticsComponent;
  let fixture: ComponentFixture<CreditsAnalyticsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [CreditsAnalyticsComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CreditsAnalyticsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
