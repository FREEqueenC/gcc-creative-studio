import { Component, OnInit, ElementRef, ViewChild, AfterViewInit } from '@angular/core';
import { Observable, of, forkJoin } from 'rxjs';
import { map, catchError, filter } from 'rxjs/operators';
import { AuthService } from '../../common/services/auth.service';
import { CreditsService, AdminOverviewStats, AdminUsageOverTime, AdminOrganizationBudget } from '../../services/credits/credits.service';
import * as d3 from 'd3';

@Component({
  selector: 'app-admin-home',
  templateUrl: './admin-home.component.html',
  styleUrls: ['./admin-home.component.scss']
})
export class AdminHomeComponent implements OnInit, AfterViewInit {
  isSuperAdmin$: Observable<boolean>;
  overviewStats$: Observable<AdminOverviewStats | null> = of(null);
  usageOverTime$: Observable<AdminUsageOverTime[] | null> = of(null);
  orgBudgets$: Observable<AdminOrganizationBudget[] | null> = of(null);

  @ViewChild('usageChart') private usageChartContainer!: ElementRef;
  @ViewChild('budgetsChart') private budgetsChartContainer!: ElementRef;

  constructor(
    private authService: AuthService,
    private creditsService: CreditsService
  ) {
    this.isSuperAdmin$ = this.authService.currentUser$.pipe(
      map(user => !!user?.isSuperAdmin)
    );
  }

  ngOnInit(): void {
    this.isSuperAdmin$.subscribe(isSuperAdmin => {
      if (isSuperAdmin) {
        this.overviewStats$ = this.creditsService.getAdminOverviewStats().pipe(
          catchError(err => {
            console.error('Error fetching overview stats:', err);
            return of(null);
          })
        );

        this.usageOverTime$ = this.creditsService.getAdminUsageOverTime().pipe(
          catchError(err => {
            console.error('Error fetching usage over time:', err);
            return of(null);
          })
        );

        this.orgBudgets$ = this.creditsService.getAdminOrganizationBudgets().pipe(
          catchError(err => {
            console.error('Error fetching organization budgets:', err);
            return of(null);
          })
        );
      }
    });
  }

  ngAfterViewInit(): void {
    this.isSuperAdmin$.pipe(
      filter(isSuperAdmin => isSuperAdmin)
    ).subscribe(() => {
      forkJoin([
        this.usageOverTime$.pipe(filter(data => !!data)),
        this.orgBudgets$.pipe(filter(data => !!data))
      ]).subscribe(([usageData, budgetData]) => {
        if (usageData) this.renderUsageChart(usageData);
        if (budgetData) this.renderBudgetsChart(budgetData);
      });
    });
  }

  private renderUsageChart(data: AdminUsageOverTime[]): void {
    if (!this.usageChartContainer) return;

    const element = this.usageChartContainer.nativeElement;
    d3.select(element).select('svg').remove(); // Clear previous chart

    const margin = { top: 20, right: 120, bottom: 40, left: 50 };
    const width = element.offsetWidth - margin.left - margin.right;
    const height = 400 - margin.top - margin.bottom;

    const svg = d3.select(element).append('svg')
      .attr('width', width + margin.left + margin.right)
      .attr('height', height + margin.top + margin.bottom)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const keys = Object.keys(data[0]).filter(k => k !== 'date');
    const colors = d3.scaleOrdinal<string>()
      .domain(keys)
      .range(['#3b82f6', '#f87171', '#8b5cf6', '#fbbf24']); // Blue, Red, Purple, Amber

    const stack = d3.stack()
      .keys(keys)
      .order(d3.stackOrderNone)
      .offset(d3.stackOffsetNone);

    const series = stack(data as any);

    const x = d3.scaleBand()
      .domain(data.map(d => d.date))
      .range([0, width])
      .padding(0.1);

    const y = d3.scaleLinear()
      .domain([0, d3.max(series, layer => d3.max(layer, d => d[1])) || 0])
      .nice()
      .range([height, 0]);

    const area = d3.area<any>()
      .x(d => x(d.data.date)! + x.bandwidth() / 2)
      .y0(d => y(d[0]))
      .y1(d => y(d[1]));

    svg.selectAll('.layer')
      .data(series)
      .join('path')
        .attr('class', 'layer')
        .attr('d', area)
        .style('fill', d => colors(d.key));

    // Axes
    svg.append('g')
      .attr('transform', `translate(0,${height})`)
      .call(d3.axisBottom(x))
      .selectAll('text')
        .style('fill', '#9ca3af');

    svg.append('g')
      .call(d3.axisLeft(y))
      .selectAll('text')
        .style('fill', '#9ca3af');

    // Legend
    const legend = svg.append('g')
      .attr('transform', `translate(${width + 20}, 0)`);

    keys.forEach((key, i) => {
      legend.append('rect')
        .attr('x', 0)
        .attr('y', i * 20)
        .attr('width', 18)
        .attr('height', 18)
        .style('fill', colors(key));

      legend.append('text')
        .attr('x', 24)
        .attr('y', i * 20 + 9)
        .attr('dy', '.35em')
        .style('text-anchor', 'start')
        .style('fill', '#e5e7eb')
        .text(key);
    });
  }

  private renderBudgetsChart(data: AdminOrganizationBudget[]): void {
    if (!this.budgetsChartContainer) return;

    const element = this.budgetsChartContainer.nativeElement;
    d3.select(element).select('svg').remove();

    const margin = { top: 20, right: 30, bottom: 100, left: 60 };
    const width = element.offsetWidth - margin.left - margin.right;
    const height = 400 - margin.top - margin.bottom;

    const svg = d3.select(element).append('svg')
      .attr('width', width + margin.left + margin.right)
      .attr('height', height + margin.top + margin.bottom)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const x = d3.scaleBand()
      .domain(data.map(d => d.orgName))
      .range([0, width])
      .padding(0.2);

    const y = d3.scaleLinear()
      .domain([0, d3.max(data, d => Math.max(d.balance, d.budget)) || 0])
      .nice()
      .range([height, 0]);

    // Balance bars
    svg.selectAll('.bar-balance')
      .data(data)
      .join('rect')
        .attr('class', 'bar-balance')
        .attr('x', d => x(d.orgName)!)
        .attr('y', d => y(d.balance))
        .attr('width', x.bandwidth() / 2)
        .attr('height', d => height - y(d.balance))
        .attr('fill', '#3b82f6'); // Blue

    // Budget bars
    svg.selectAll('.bar-budget')
      .data(data)
      .join('rect')
        .attr('class', 'bar-budget')
        .attr('x', d => x(d.orgName)! + x.bandwidth() / 2)
        .attr('y', d => y(d.budget))
        .attr('width', x.bandwidth() / 2)
        .attr('height', d => height - y(d.budget))
        .attr('fill', '#8b5cf6'); // Purple

    // Axes
    svg.append('g')
      .attr('transform', `translate(0,${height})`)
      .call(d3.axisBottom(x))
      .selectAll('text')
        .attr('transform', 'rotate(-45)')
        .style('text-anchor', 'end')
        .style('fill', '#9ca3af');

    svg.append('g')
      .call(d3.axisLeft(y))
      .selectAll('text')
        .style('fill', '#9ca3af');

    // Legend
    const legend = svg.append('g')
      .attr('transform', `translate(0, -10)`);

    legend.append('rect').attr('x', 0).attr('y', -10).attr('width', 18).attr('height', 18).style('fill', '#3b82f6');
    legend.append('text').attr('x', 24).attr('y', 0).attr('dy', '.35em').style('fill', '#e5e7eb').text('Balance');
    legend.append('rect').attr('x', 100).attr('y', -10).attr('width', 18).attr('height', 18).style('fill', '#8b5cf6');
    legend.append('text').attr('x', 124).attr('y', 0).attr('dy', '.35em').style('fill', '#e5e7eb').text('Budget');
  }
}
