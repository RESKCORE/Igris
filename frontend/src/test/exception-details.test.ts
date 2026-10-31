import { describe, expect, it } from 'vitest';
import { demoExceptions } from '@/lib/demo-workspace';
import { exceptionDetails, filterExceptions } from '@/lib/exception-details';

describe('Exception filters', () => {
  it('All includes every status', () => {
    expect(filterExceptions(demoExceptions, 'all', '')).toHaveLength(4);
  });
  it('Open only includes open exceptions', () => {
    expect(filterExceptions(demoExceptions, 'open', '').map(item => item.id)).toEqual(['ex-demo-1', 'ex-demo-2', 'ex-demo-3']);
  });
  it('Fixed only includes fixed exceptions', () => {
    expect(filterExceptions(demoExceptions, 'fixed', '').map(item => item.id)).toEqual(['ex-demo-4']);
  });
  it('Rejected only includes rejected exceptions', () => {
    const first = demoExceptions[0];
    if (!first) throw new Error('Expected a sample exception');
    const rejected = { ...first, status: 'rejected' as const };
    expect(filterExceptions([...demoExceptions, rejected], 'rejected', '')).toEqual([rejected]);
  });
  it('searches reference IDs and names without case sensitivity', () => {
    expect(filterExceptions(demoExceptions, 'all', ' inv-106 ').map(item => item.id)).toEqual(['ex-demo-1']);
    expect(filterExceptions(demoExceptions, 'open', 'priya').map(item => item.id)).toEqual(['ex-demo-1']);
    expect(filterExceptions(demoExceptions, 'fixed', 'priya')).toEqual([]);
  });
});

describe('Readable exception values', () => {
  it('formats money and numbers while preserving the negative sign', () => {
    expect(exceptionDetails({ amount: -120, quantity: 12500 })).toEqual([{ label: 'amount', value: '-$120.00' }, { label: 'quantity', value: '12,500' }]);
  });
  it('formats nested values without raw JSON', () => {
    expect(exceptionDetails({ customer: { full_name: 'Priya Nair' }, active: true })).toEqual([{ label: 'customer · full name', value: 'Priya Nair' }, { label: 'active', value: 'Yes' }]);
  });
});