import { Check, Lightbulb, Loader2, X } from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { exceptionDetails } from '@/lib/exception-details';
import { cn } from '@/lib/utils';
import type { ExceptionItem } from '@/lib/types';

export function ExceptionCard({ item, busy, onResolve }: {
  item: ExceptionItem;
  busy: boolean;
  onResolve: (id: string, status: 'fixed' | 'rejected') => void;
}) {
  const reducedMotion = useReducedMotion();
  const tone = item.status === 'open' ? 'bg-warning-soft text-warning' : item.status === 'rejected' ? 'bg-danger-soft text-danger' : 'bg-lime-soft text-lime-foreground';
  return <motion.article layout={!reducedMotion} initial={reducedMotion ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reducedMotion ? 0 : 0.25 }} className="flex min-w-0 flex-col overflow-hidden rounded-3xl border border-border bg-card shadow-dashboard">
    <header className="flex flex-wrap items-center gap-2 border-b border-border px-5 py-4 sm:px-6">
      <span className="mr-auto font-mono text-sm font-medium">{item.rowRef}</span>
      <span className="rounded-full bg-muted px-2.5 py-1 font-mono text-[11px] text-muted-foreground">{item.runId}</span>
      <span className={cn('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold capitalize', tone)}><span className="size-1.5 rounded-full bg-current" />{item.status}</span>
    </header>
    <div className="flex-1 p-5 sm:p-6">
      <h2 className="mb-5 text-xl font-semibold">{item.reason}</h2>
      <dl className="space-y-3.5">{exceptionDetails(item.rawData).map(detail => <div key={detail.label} className="flex min-w-0 flex-wrap items-start justify-between gap-x-4 gap-y-1.5">
        <dt className="rounded-md bg-muted px-2 py-1 text-xs font-medium capitalize text-muted-foreground">{detail.label}</dt>
        <dd className="min-w-0 max-w-full py-0.5 text-right text-sm font-medium tabular-nums [overflow-wrap:anywhere]">{detail.value}</dd>
      </div>)}</dl>
      {item.suggestedFix && <aside className="mt-6 flex gap-3 rounded-xl border border-lime/30 bg-lime-soft/40 p-4">
        <Lightbulb className="mt-0.5 size-4 shrink-0 text-forest" aria-hidden="true" />
        <div className="min-w-0"><p className="text-xs font-semibold text-forest">Suggested resolution</p><p className="mt-1 text-sm leading-relaxed [overflow-wrap:anywhere]">{item.suggestedFix}</p></div>
      </aside>}
    </div>
    <footer className="flex min-h-20 flex-wrap items-center gap-3 border-t border-border px-5 py-4 sm:px-6">
      {item.status === 'open' ? <>
        <Button disabled={busy} onClick={() => onResolve(item.id, 'fixed')} className="rounded-full shadow-dashboard-action">{busy ? <Loader2 className="animate-spin" /> : <Check />}Mark fixed</Button>
        <Button variant="outline" disabled={busy} onClick={() => onResolve(item.id, 'rejected')} className="rounded-full bg-card"><X />Reject</Button>
      </> : <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">{item.status === 'rejected' ? <X className="size-4" /> : <Check className="size-4 text-forest" />} {item.status === 'fixed' ? 'Marked as fixed' : item.status === 'rejected' ? 'Rejected' : 'Approved'}</span>}
    </footer>
  </motion.article>;
}