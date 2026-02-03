import { Component, OnInit, ElementRef, ViewChild, AfterViewInit, OnDestroy, Inject, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { Observable, of, forkJoin } from 'rxjs';
import { map, catchError, filter } from 'rxjs/operators';
import { AuthService } from '../../common/services/auth.service';
import { CreditsService, AdminOverviewStats, AdminUsageOverTime, AdminOrganizationBudget, AdminActiveRole } from '../../services/credits/credits.service';
import * as d3 from 'd3';

@Component({
  selector: 'app-admin-home',
  templateUrl: './admin-home.component.html',
  styleUrls: ['./admin-home.component.scss']
})
export class AdminHomeComponent implements OnInit, AfterViewInit, OnDestroy {
  isSuperAdmin$: Observable<boolean>;
  overviewStats$: Observable<AdminOverviewStats | null> = of(null);
  usageOverTime$: Observable<AdminUsageOverTime[] | null> = of(null);
  orgBudgets$: Observable<AdminOrganizationBudget[] | null> = of(null);
  activeRoles$: Observable<AdminActiveRole[] | null> = of(null);

  @ViewChild('usageChart') private usageChartContainer!: ElementRef;
  @ViewChild('budgetsChart') private budgetsChartContainer!: ElementRef;
  @ViewChild('rolesChart') private rolesChartContainer!: ElementRef;
  @ViewChild('combinedMediaChart') private combinedMediaChartContainer!: ElementRef;

  constructor(
    private authService: AuthService,
    private creditsService: CreditsService,
    @Inject(PLATFORM_ID) private platformId: Object
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

        this.activeRoles$ = this.creditsService.getAdminActiveRoles().pipe(
          catchError(err => {
            console.error('Error fetching active roles:', err);
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
        this.orgBudgets$.pipe(filter(data => !!data)),
        this.activeRoles$.pipe(filter(data => !!data))
      ]).subscribe(([usageData, budgetData, rolesData]) => {
        if (usageData) {
          this.renderUsageChart(usageData);
          this.renderTotalMediaChart(usageData);
        }
        if (budgetData) this.renderBudgetsChart(budgetData);
        if (rolesData) this.renderActiveRolesChart(rolesData);
      });
    });
  }

  private renderUsageChart(data: AdminUsageOverTime[]): void {
    if (!this.usageChartContainer) return;

    const element = this.usageChartContainer.nativeElement;
    d3.select(element).select('svg').remove(); 

    const margin = { top: 20, right: 150, bottom: 40, left: 60 };
    const width = element.offsetWidth - margin.left - margin.right;
    const height = 400 - margin.top - margin.bottom;

    const svg = d3.select(element).append('svg')
      .attr('width', width + margin.left + margin.right)
      .attr('height', height + margin.top + margin.bottom)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const keys = Object.keys(data[0]).filter(k => k !== 'date' && k !== 'Total');
    const colors = d3.scaleOrdinal<string>()
      .domain(keys)
      .range(['#3b82f6', '#f87171', '#8b5cf6', '#fbbf24']); 

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

    // Tooltip
    const tooltip = d3.select('body').append('div')
      .attr('class', 'chart-tooltip absolute bg-white text-black border border-gray-300 rounded px-2 py-1 opacity-0 pointer-events-none')
      .style('z-index', '1000');

    svg.selectAll('.layer')
      .data(series)
      .join('path')
        .attr('class', 'layer')
        .attr('d', area)
        .style('fill', d => colors(d.key))
        .on('mouseover', (event, d) => {
          tooltip.style('opacity', 1);
          d3.select(event.currentTarget).style('opacity', 0.8);
        })
        .on('mousemove', (event, d) => {
          const key = d.key;
          const mouseX = d3.pointer(event, svg.node())[0];
          const date = x.domain()[Math.floor(mouseX / x.step())];
          const dataPoint = data.find(item => item.date === date);
          const value = dataPoint ? dataPoint[key] : 0;
          tooltip
            .html(`Date: ${date}<br>${key}: ${value}`)
            .style('left', (event.pageX + 10) + 'px')
            .style('top', (event.pageY - 28) + 'px');
        })
        .on('mouseleave', (event, d) => {
          tooltip.style('opacity', 0);
          d3.select(event.currentTarget).style('opacity', 1);
        });

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
    svg.append('text')
        .attr('transform', 'rotate(-90)')
        .attr('y', 0 - margin.left)
        .attr('x', 0 - (height / 2))
        .attr('dy', '1em')
        .style('text-anchor', 'middle')
        .style('fill', '#9ca3af')
        .text('Credits Spent');

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

    const margin = { top: 30, right: 30, bottom: 120, left: 60 };
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
      .padding(0.3);

    const y = d3.scaleLinear()
      .domain([0, d3.max(data, d => Math.max(d.balance, d.budget)) || 0])
      .nice()
      .range([height, 0]);

    // Tooltip
    const tooltip = d3.select('body').append('div')
      .attr('class', 'chart-tooltip absolute bg-white text-black border border-gray-300 rounded px-2 py-1 opacity-0 pointer-events-none')
      .style('z-index', '1000');

    const mouseover = (event: any, d: any) => {
      tooltip.style('opacity', 1);
      d3.select(event.currentTarget).style('opacity', 0.7);
    };
    const mouseleave = (event: any, d: any) => {
      tooltip.style('opacity', 0);
      d3.select(event.currentTarget).style('opacity', 1);
    };

    // Balance bars
    svg.selectAll('.bar-balance')
      .data(data)
      .join('rect')
        .attr('class', 'bar-balance')
        .attr('x', d => x(d.orgName)!)
        .attr('y', d => y(d.balance))
        .attr('width', x.bandwidth() / 2)
        .attr('height', d => height - y(d.balance))
        .attr('fill', '#3b82f6') // Blue
        .on('mouseover', mouseover)
        .on('mousemove', (event, d) => {
          tooltip
            .html(`Org: ${d.orgName}<br>Balance: $${d.balance.toFixed(2)}`)
            .style('left', (event.pageX + 10) + 'px')
            .style('top', (event.pageY - 28) + 'px');
        })
        .on('mouseleave', mouseleave);

    // Budget bars
    svg.selectAll('.bar-budget')
      .data(data)
      .join('rect')
        .attr('class', 'bar-budget')
        .attr('x', d => x(d.orgName)! + x.bandwidth() / 2)
        .attr('y', d => y(d.budget))
        .attr('width', x.bandwidth() / 2)
        .attr('height', d => height - y(d.budget))
        .attr('fill', '#8b5cf6') // Purple
        .on('mouseover', mouseover)
        .on('mousemove', (event, d) => {
          tooltip
            .html(`Org: ${d.orgName}<br>Budget: $${d.budget.toFixed(2)}`)
            .style('left', (event.pageX + 10) + 'px')
            .style('top', (event.pageY - 28) + 'px');
        })
        .on('mouseleave', mouseleave);

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
    svg.append('text')
        .attr('transform', 'rotate(-90)')
        .attr('y', 0 - margin.left)
        .attr('x', 0 - (height / 2))
        .attr('dy', '1em')
        .style('text-anchor', 'middle')
        .style('fill', '#9ca3af')
        .text('Amount (USD)');

    // Legend
    const legend = svg.append('g')
      .attr('transform', `translate(0, -20)`);

    legend.append('rect').attr('x', 0).attr('y', 0).attr('width', 18).attr('height', 18).style('fill', '#3b82f6');
    legend.append('text').attr('x', 24).attr('y', 9).attr('dy', '.35em').style('fill', '#e5e7eb').text('Balance');
    legend.append('rect').attr('x', 100).attr('y', 0).attr('width', 18).attr('height', 18).style('fill', '#8b5cf6');
    legend.append('text').attr('x', 124).attr('y', 9).attr('dy', '.35em').style('fill', '#e5e7eb').text('Budget');
  }

  private renderActiveRolesChart(data: AdminActiveRole[]): void {
    if (!this.rolesChartContainer) return;

    const element = this.rolesChartContainer.nativeElement;
    d3.select(element).select('svg').remove();

    const width = element.offsetWidth;
    const height = 400;
    const margin = 40;
    const radius = Math.min(width, height) / 2 - margin;

    const svg = d3.select(element).append('svg')
      .attr('width', width)
      .attr('height', height)
      .append('g')
      .attr('transform', `translate(${width / 2}, ${height / 2})`);

    const colors = d3.scaleOrdinal<string>()
      .domain(data.map(d => d.role))
      .range(['#3b82f6', '#f87171', '#8b5cf6', '#fbbf24', '#4ade80']);

    const pie = d3.pie<AdminActiveRole>()
      .value(d => d.count);

    const arcGenerator = d3.arc<any>()
      .innerRadius(radius * 0.4)
      .outerRadius(radius * 0.8);

    const tooltip = d3.select('body').append('div')
      .attr('class', 'chart-tooltip absolute bg-white text-black border border-gray-300 rounded px-2 py-1 opacity-0 pointer-events-none')
      .style('z-index', '1000');

    svg.selectAll('slices')
      .data(pie(data))
      .join('path')
        .attr('d', arcGenerator)
        .attr('fill', d => colors(d.data.role))
        .attr('stroke', '#1E1F22')
        .style('stroke-width', '2px')
        .style('opacity', 0.8)
        .on('mouseover', (event, d) => {
          tooltip.style('opacity', 1);
          d3.select(event.currentTarget).style('opacity', 1);
        })
        .on('mousemove', (event, d) => {
          tooltip
            .html(`${d.data.role}: ${d.data.count}`)
            .style('left', (event.pageX + 10) + 'px')
            .style('top', (event.pageY - 28) + 'px');
        })
        .on('mouseleave', (event, d) => {
          tooltip.style('opacity', 0);
          d3.select(event.currentTarget).style('opacity', 0.8);
        });

    // Legend
    const legendContainer = d3.select(element).append('div')
      .attr('class', 'legend-container mt-4 flex flex-wrap justify-center');

    const legendItems = legendContainer.selectAll('.legend-item')
      .data(data)
      .enter().append('div')
        .attr('class', 'legend-item flex items-center mr-4 mb-2');

    legendItems.append('span')
      .style('display', 'inline-block')
      .style('width', '12px')
      .style('height', '12px')
      .style('background-color', d => colors(d.role))
      .style('margin-right', '6px');

    legendItems.append('span')
      .text(d => `${d.role} (${d.count})`)
      .style('color', '#e5e7eb')
      .style('font-size', '12px');
  }

  private renderTotalMediaChart(data: AdminUsageOverTime[]): void {
    if (!this.combinedMediaChartContainer) return;

    const element = this.combinedMediaChartContainer.nativeElement;
    d3.select(element).select('svg').remove();

    const margin = { top: 20, right: 150, bottom: 40, left: 60 };
    const width = element.offsetWidth - margin.left - margin.right;
    const height = 400 - margin.top - margin.bottom;

    const svg = d3.select(element).append('svg')
      .attr('width', width + margin.left + margin.right)
      .attr('height', height + margin.top + margin.bottom)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    if (!data || data.length === 0) {
      console.error('No data for renderTotalMediaChart');
      return;
    }
    const keys = Object.keys(data[0]).filter(k => k !== 'date');
    const colors = d3.scaleOrdinal<string>()
      .domain(keys)
      .range(['#3b82f6', '#f87171', '#8b5cf6', '#fbbf24', '#4ade80', '#e11d48', '#ff6347']); // Added more colors

    const x = d3.scalePoint()
      .domain(data.map(d => d.date))
      .range([0, width]);

    const yMax = d3.max(data, d => {
      return d3.max(keys, key => d[key] as number || 0);
    }) || 0;
    const yDomain = [0, yMax];
    const y = d3.scaleLinear()
      .domain(yDomain)
      .nice()
      .range([height, 0]);

    // Add X axis
    svg.append('g')
      .attr('transform', `translate(0,${height})`)
      .call(d3.axisBottom(x))
      .selectAll('text')
        .style('fill', '#9ca3af');

    // Add Y axis
    svg.append('g')
      .call(d3.axisLeft(y))
      .selectAll('text')
        .style('fill', '#9ca3af');
    svg.append('text')
        .attr('transform', 'rotate(-90)')
        .attr('y', 0 - margin.left)
        .attr('x', 0 - (height / 2))
        .attr('dy', '1em')
        .style('text-anchor', 'middle')
        .style('fill', '#9ca3af')
        .text('Credits Spent');

    // Tooltip
    const tooltip = d3.select('body').append('div')
      .attr('class', 'chart-tooltip absolute bg-white text-black border border-gray-300 rounded px-2 py-1 opacity-0 pointer-events-none')
      .style('z-index', '1000');

    // Draw lines for each key
    keys.forEach(key => {
      const line = d3.line<AdminUsageOverTime>()
        .x(d => x(d.date)!)
        .y(d => {
          const val = y(d[key] as number || 0);
          return val;
        });

      const pathData = line(data);

      svg.append('path')
        .datum(data)
        .attr('fill', 'none')
        .attr('stroke', key === 'Total' ? 'lime' : colors(key))
        .attr('stroke-width', key === 'Total' ? 5 : 1.5)
        .attr('d', line)
        .on('mouseover', (event, d) => {
          tooltip.style('opacity', 1);
          d3.select(event.currentTarget).style('stroke-width', key === 'Total' ? 4.5 : 3);
        })
        .on('mousemove', (event, d) => {
          const mouseX = d3.pointer(event, svg.node())[0];
          const dates = data.map(item => item.date);
          const closestDate = dates.reduce((a, b) => Math.abs(x(a)! - mouseX) < Math.abs(x(b)! - mouseX) ? a : b);
          const dataPoint = data.find(item => item.date === closestDate);
          if (!dataPoint) return;

          let html = `Date: ${closestDate}<br>`;
          keys.forEach(k => {
            html += `${k}: ${dataPoint[k] || 0}<br>`;
          });

          tooltip
            .html(html)
            .style('left', (event.pageX + 10) + 'px')
            .style('top', (event.pageY - 28) + 'px');
        })
        .on('mouseleave', (event, d) => {
          tooltip.style('opacity', 0);
          d3.select(event.currentTarget).style('stroke-width', key === 'Total' ? 3 : 1.5);
        });
    });

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

  ngOnDestroy(): void {
    if (isPlatformBrowser(this.platformId)) {
      d3.select('body').selectAll('.chart-tooltip').remove();
    }
  }
}
