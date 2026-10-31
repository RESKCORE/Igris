import { useState } from 'react';
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Pie, PieChart, XAxis, YAxis } from 'recharts';
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from '@/components/ui/chart';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { getDashboardMetrics, getRunActivity } from '@/lib/dashboard-metrics';
import type { Dataset, Run } from '@/lib/types';

const qualityConfig = {
  valid: { label: 'Valid', color: 'var(--forest)' },
  warning: { label: 'Warnings', color: 'var(--warning)' },
  error: { label: 'Errors', color: 'var(--danger)' },
} satisfies ChartConfig;
const stateConfig = {
  planned: { label: 'Planned', color: 'var(--lime)' },
  approved: { label: 'Approved', color: 'var(--info)' },
  executed: { label: 'Completed', color: 'var(--forest)' },
} satisfies ChartConfig;
const activityConfig = {
  created: { label: 'Created', color: 'var(--forest)' },
  completed: { label: 'Completed', color: 'var(--lime)' },
} satisfies ChartConfig;

export function DashboardCharts({ datasets, runs }: { datasets: Dataset[]; runs: Run[] }) {
  const [range, setRange] = useState('7');
  const metrics = getDashboardMetrics(datasets, runs);
  const activity = getRunActivity(runs, Number(range));
  const visibleRuns = activity.reduce((sum, day) => sum + day.created, 0);
  return (
    <div className="grid min-w-0 gap-5">
      <div className="grid min-w-0 gap-5 lg:grid-cols-[1.65fr_1fr]">
        <section className="panel min-w-0" aria-label="Workflow activity chart">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div><h2 className="text-lg font-semibold">Workflow activity</h2><p className="mt-1 text-xs text-muted-foreground">Daily runs · through {activity.at(-1)?.date} (UTC)</p></div>
            <Tabs value={range} onValueChange={setRange}><TabsList className="rounded-full"><TabsTrigger value="7" className="rounded-full">7 days</TabsTrigger><TabsTrigger value="30" className="rounded-full">30 days</TabsTrigger></TabsList></Tabs>
          </div>
          <div className="mt-5 flex items-baseline gap-2"><span className="text-3xl font-semibold tabular-nums">{visibleRuns}</span><span className="text-sm text-muted-foreground">runs in this period</span></div>
          <ChartContainer config={activityConfig} className="mt-4 h-52 w-full aspect-auto">
            <AreaChart accessibilityLayer data={activity} margin={{ left: -20, right: 10, top: 10, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 3" />
              <XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={35} tickMargin={12} />
              <YAxis tickLine={false} axisLine={false} allowDecimals={false} tickMargin={8} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Area dataKey="created" type="monotone" fill="var(--color-created)" fillOpacity={0.08} stroke="var(--color-created)" strokeWidth={2.5} isAnimationActive={false} />
              <Area dataKey="completed" type="monotone" fill="var(--color-completed)" fillOpacity={0.2} stroke="var(--color-completed)" strokeWidth={2.5} isAnimationActive={false} />
            </AreaChart>
          </ChartContainer>
          <div className="mt-3 flex gap-5 text-xs text-muted-foreground"><span className="flex items-center gap-2"><i className="size-2 rounded-full bg-forest" />Created</span><span className="flex items-center gap-2"><i className="size-2 rounded-full bg-lime" />Completed</span></div>
        </section>
        <section className="panel min-w-0" aria-label="Run status chart">
          <h2 className="text-lg font-semibold">Run overview</h2><p className="mt-1 text-xs text-muted-foreground">Current workflow status</p>
          <div className="relative mt-3">
            <ChartContainer config={stateConfig} className="h-52 w-full aspect-auto">
              <PieChart accessibilityLayer><ChartTooltip content={<ChartTooltipContent hideLabel nameKey="state" />} /><Pie data={metrics.states} dataKey="count" nameKey="state" innerRadius={65} outerRadius={86} paddingAngle={5} stroke="var(--card)" strokeWidth={3} isAnimationActive={false} /></PieChart>
            </ChartContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center"><span className="text-3xl font-semibold tabular-nums">{runs.length}</span><span className="text-xs text-muted-foreground">total runs</span></div>
          </div>
          <div className="mt-2 grid gap-2.5 text-sm">{metrics.states.map(item => <div key={item.state} className="flex items-center justify-between"><span className="flex items-center gap-2 text-muted-foreground"><i className={`size-2 rounded-full ${item.state === 'planned' ? 'bg-lime' : item.state === 'approved' ? 'bg-info' : 'bg-forest'}`} />{stateConfig[item.state as keyof typeof stateConfig].label}</span><span className="font-semibold tabular-nums">{item.count}</span></div>)}</div>
        </section>
      </div>
      <section className="panel min-w-0" aria-label="Dataset quality chart">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-semibold">Data health</h2><p className="mt-1 text-xs text-muted-foreground">Record validation across your datasets</p></div><span className="rounded-full bg-lime-soft px-3 py-1 text-xs font-medium text-lime-foreground">{metrics.quality}% valid records</span></div>
        {datasets.length ? <ChartContainer config={qualityConfig} className="mt-5 h-48 w-full aspect-auto"><BarChart accessibilityLayer data={metrics.datasets} margin={{ left: -20, right: 12, top: 5 }} barSize={44}><CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 3" /><XAxis dataKey="name" tickLine={false} axisLine={false} tickMargin={12} /><YAxis tickLine={false} axisLine={false} allowDecimals={false} /><ChartTooltip content={<ChartTooltipContent />} /><Bar dataKey="valid" stackId="quality" fill="var(--color-valid)" isAnimationActive={false} /><Bar dataKey="warning" stackId="quality" fill="var(--color-warning)" isAnimationActive={false} /><Bar dataKey="error" stackId="quality" fill="var(--color-error)" radius={[4, 4, 0, 0]} isAnimationActive={false} /></BarChart></ChartContainer> : <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">No datasets loaded</div>}
        <div className="mt-4 flex gap-5 text-xs text-muted-foreground"><span className="flex items-center gap-2"><i className="size-2 rounded-full bg-forest" />Valid</span><span className="flex items-center gap-2"><i className="size-2 rounded-full bg-warning" />Warnings</span><span className="flex items-center gap-2"><i className="size-2 rounded-full bg-danger" />Errors</span></div>
      </section>
    </div>
  );
}