import type { Dataset, Run } from './types';

export function getDashboardMetrics(datasets: Dataset[], runs: Run[]) {
  const rows = datasets.flatMap(dataset => dataset.rows);
  const valid = rows.filter(row => row.validationStatus === 'ok').length;
  return {
    total: rows.length,
    valid,
    quality: rows.length ? Math.round(valid / rows.length * 100) : 0,
    completed: runs.filter(run => run.state === 'executed').length,
    datasets: datasets.map(dataset => ({
      name: dataset.name,
      valid: dataset.rows.filter(row => row.validationStatus === 'ok').length,
      warning: dataset.rows.filter(row => row.validationStatus === 'warning').length,
      error: dataset.rows.filter(row => row.validationStatus === 'error').length,
    })),
    states: ['planned', 'approved', 'executed'].map(state => ({
      state,
      count: runs.filter(run => run.state === state).length,
      fill: `var(--color-${state})`,
    })),
  };
}

export function getRunActivity(runs: Run[], days: number) {
  const latest = runs.reduce((max, run) => Math.max(max, new Date(run.createdAt).getTime()), 0);
  const end = new Date(latest || Date.now());
  end.setUTCHours(0, 0, 0, 0);
  return Array.from({ length: days }, (_, index) => {
    const date = new Date(end);
    date.setUTCDate(date.getUTCDate() - (days - 1 - index));
    const key = date.toISOString().slice(0, 10);
    const daily = runs.filter(run => run.createdAt.slice(0, 10) === key);
    return {
      date: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' }),
      created: daily.length,
      completed: daily.filter(run => run.state === 'executed').length,
    };
  });
}