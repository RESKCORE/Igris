import { describe, expect, it } from 'vitest';
import { api } from '@/lib/api';

describe('Sample workspace', () => {
  it('starts with records for all remaining workspace pages', async () => {
    expect((await api.listDatasets()).length).toBe(4);
    const runs = await api.listRuns();
    expect(runs.length).toBe(3);
    expect((await api.getRun('run-demo-1'))?.plan.tasks.length).toBeGreaterThan(0);
    expect((await api.getExceptions()).length).toBe(4);
    expect((await api.getOutbox()).length).toBe(3);
    expect((await api.getAudit()).length).toBeGreaterThanOrEqual(5);
    expect(await api.verifyAudit()).toEqual({ valid: true });
  });
});