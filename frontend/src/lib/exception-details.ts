import type { ExceptionItem } from './types';

export type ExceptionFilter = 'all' | 'open' | 'fixed' | 'rejected';

export function filterExceptions(items: ExceptionItem[], status: ExceptionFilter, search: string) {
  const query = search.trim().toLocaleLowerCase();
  return items.filter(item => (status === 'all' || item.status === status) &&
    [item.id, item.rowRef, item.runId, item.reason, ...exceptionDetails(item.rawData).map(detail => detail.value)]
      .some(value => value.toLocaleLowerCase().includes(query)));
}

export function exceptionDetails(data: Record<string, unknown>, prefix = ''): { label: string; value: string }[] {
  return Object.entries(data).flatMap(([key, value]) => {
    const label = `${prefix}${key.replace(/([a-z])([A-Z])/g, '$1 $2').replaceAll('_', ' ')}`;
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return exceptionDetails(value as Record<string, unknown>, `${label} · `);
    }
    const format = (entry: unknown): string => {
      if (entry === null || entry === undefined || entry === '') return '—';
      if (typeof entry === 'number') {
        const currency = /amount|price|total|balance|cost/i.test(key);
        const currencyCode = typeof data['currency'] === 'string' && /^[A-Z]{3}$/.test(data['currency']) ? data['currency'] : 'USD';
        return new Intl.NumberFormat('en-US', currency ? { style: 'currency', currency: currencyCode } : { maximumFractionDigits: 2 }).format(entry);
      }
      if (typeof entry === 'boolean') return entry ? 'Yes' : 'No';
      if (typeof entry === 'object') return exceptionDetails(entry as Record<string, unknown>).map(detail => `${detail.label}: ${detail.value}`).join(' · ');
      return String(entry);
    };
    return [{ label, value: Array.isArray(value) ? value.map(format).join(', ') || '—' : format(value) }];
  });
}