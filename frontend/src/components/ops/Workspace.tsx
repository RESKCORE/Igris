import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export function pageHead(title: string, description: string) {
  return { meta: [{ title: `${title} · Igris` }, { name: 'description', content: description }, { property: 'og:title', content: `${title} · Igris` }, { property: 'og:description', content: description }, { property: 'og:type', content: 'website' }, { name: 'twitter:card', content: 'summary_large_image' }] };
}
export function PageHeading({ title, subtitle, children }: { title: string; subtitle: string; children?: ReactNode }) {
  return <header className="mb-6 flex flex-wrap items-center justify-between gap-4"><div><h1 className="text-3xl font-semibold">{title}</h1><p className="mt-1 text-sm text-muted-foreground">{subtitle}</p></div>{children}</header>;
}
export function Status({ value }: { value: string }) {
  const tone = value === 'error' || value === 'open' || value === 'rejected' ? 'bg-danger-soft text-danger' : value === 'warning' ? 'bg-warning-soft text-warning' : value === 'simulated' || value === 'planned' || value === 'pending' ? 'bg-info-soft text-info' : 'bg-lime-soft text-lime-foreground';
  return <span className={cn('inline-flex rounded-full px-3 py-1 text-xs font-medium capitalize', tone)}>{value === 'ok' ? 'Valid' : value.replaceAll('_', ' ')}</span>;
}
export function Metrics({ items }: { items: { label: string; value: number | string }[] }) {
  return <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">{items.map(item => <div className="panel" key={item.label}><p className="text-sm text-muted-foreground">{item.label}</p><p className="mt-2 text-3xl font-semibold">{item.value}</p></div>)}</div>;
}
export function downloadFile(name: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click(); URL.revokeObjectURL(url);
}