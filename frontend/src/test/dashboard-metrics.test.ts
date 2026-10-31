import { describe, expect, it } from 'vitest';
import { getDashboardMetrics, getRunActivity } from '@/lib/dashboard-metrics';
import { demoRuns } from '@/lib/demo-workspace';
import type { Dataset } from '@/lib/types';

describe('Dashboard aggregations', () => {
  it('counts validation statuses from the actual dataset rows', () => {
    const datasets: Dataset[] = [{ id: 'test', name: 'Test', columns: [], rows: [
      { id: '1', data: {}, issues: [], validationStatus: 'ok' },
      { id: '2', data: {}, issues: [], validationStatus: 'warning' },
      { id: '3', data: {}, issues: [], validationStatus: 'error' },
    ] }];
    const metrics = getDashboardMetrics(datasets, demoRuns);
    expect(metrics.total).toBe(3);
    expect(metrics.quality).toBe(33);
    expect(metrics.completed).toBe(1);
    expect(metrics.datasets[0]).toEqual({ name: 'Test', valid: 1, warning: 1, error: 1 });
  });
  it('groups runs by UTC date and preserves totals when changing ranges', () => {
    const activity = getRunActivity(demoRuns, 7);
    expect(activity).toHaveLength(7);
    expect(activity.at(-1)).toEqual({ date: 'Oct 31', created: 2, completed: 0 });
    expect(activity.at(-2)).toEqual({ date: 'Oct 30', created: 1, completed: 1 });
    expect(getRunActivity(demoRuns, 30).reduce((sum, day) => sum + day.created, 0)).toBe(3);
  });
  it('returns safe zero counts for an empty workspace', () => {
    expect(getDashboardMetrics([], []).quality).toBe(0);
    expect(getRunActivity([], 7).every(day => day.created === 0)).toBe(true);
  });
});