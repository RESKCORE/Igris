import { Button } from '@/components/ui/button';
import { createFileRoute, Link } from '@tanstack/react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { toast } from 'sonner';
import { Loader2, Send } from 'lucide-react';
import { api } from '@/lib/api';
import { useOps } from '@/lib/mode-store';
import { RiskBadge } from '@/components/ops/AppShell';
import { PageHeading, Status, pageHead } from '@/components/ops/Workspace';
import type { Mode } from '@/lib/types';

export const Route = createFileRoute('/plan')({ head: () => pageHead('Plan', 'Review every workflow step and its risk before approving it.'), component: PlanPage });

const MODES: { value: Mode; label: string; hint: string }[] = [
  { value: 'simulation', label: 'Simulation', hint: 'Recorded in SQL, nothing sent' },
  { value: 'sandbox', label: 'Sandbox', hint: 'Real send, every recipient rewritten to your safe inbox' },
  { value: 'live', label: 'Live', hint: 'True recipients - needs ALLOW_LIVE and confirmation' },
];

function PlanPage() {
  const qc = useQueryClient(); const { runId, setRunId } = useOps();
  const runs = useQuery({ queryKey: ['runs'], queryFn: () => api.listRuns() });
  const id = runId ?? runs.data?.[0]?.id;
  const detail = useQuery({ queryKey: ['run', id], queryFn: () => id ? api.getRun(id) : Promise.resolve(null), enabled: !!id });
  const approve = useMutation({ mutationFn: () => id ? api.approvePlan(id) : Promise.reject(new Error('Select a run first')), onSuccess: () => { qc.invalidateQueries(); toast.success('Plan approved'); }, onError: (e) => toast.error('Approval failed', { description: e instanceof Error ? e.message : String(e) }) });
  const plan = detail.data?.plan;
  const run = detail.data?.run;

  const [mode, setMode] = useState<Mode>('simulation');
  const [confirmLive, setConfirmLive] = useState(false);
  const preview = useQuery({ queryKey: ['preview', id], queryFn: () => api.getPreview(id!), enabled: !!id, staleTime: 10_000 });
  const execute = useMutation({
    mutationFn: () => { if (!id) return Promise.reject(new Error('Select a run first')); return api.execute(id, mode, confirmLive); },
    onSuccess: (msgs) => {
      qc.invalidateQueries();
      const failed = msgs.filter(m => m.status === 'failed').length;
      failed ? toast.error(`${failed} message${failed > 1 ? 's' : ''} failed to deliver`) : toast.success(`${msgs.length} message${msgs.length === 1 ? '' : 's'} sent by ${mode}`);
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Execution failed'),
  });

  const modeHint = MODES.find(m => m.value === mode)!.hint;
  return <div><PageHeading title="Plan" subtitle="Nothing runs until the steps are reviewed and approved.">
    <select aria-label="Choose run" value={id ?? ''} onChange={e => setRunId(e.target.value)} className="h-10 rounded-full border bg-card px-4 text-sm">{runs.data?.map(r => <option key={r.id} value={r.id}>{r.id} · {r.state}</option>)}</select></PageHeading>
    {plan && <section className="panel"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-sm text-muted-foreground">Request</p><h2 className="mt-1 max-w-3xl text-xl font-medium">{plan.instruction}</h2></div><Status value={plan.approved ? 'approved' : 'planned'} /></div>
      <ol className="mt-6 grid gap-3">{plan.tasks.map((t, i) => <li key={t.id} className="flex flex-wrap items-center gap-4 rounded-2xl bg-muted p-4"><span className="flex size-9 items-center justify-center rounded-full bg-card font-semibold">{i + 1}</span><div className="min-w-0 flex-1"><p className="font-medium">{t.description}</p><p className="font-mono text-xs text-muted-foreground">{t.action}</p></div><RiskBadge risk={t.risk} /></li>)}</ol>
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Button disabled={plan.approved || approve.isPending} onClick={() => approve.mutate()} className="rounded-full bg-forest px-5 py-2.5 text-sm font-medium text-forest-foreground disabled:opacity-50">{plan.approved ? 'Approved' : 'Approve plan'}</Button>
        {run && <p className="text-xs text-muted-foreground">Run state: {run.state}<span className="inline-flex size-2 rounded-full bg-success" /></p>}
      </div>
      {plan.approved && <div className="mt-5 rounded-2xl bg-muted p-5">
        <div className="flex items-center justify-between gap-3">
          <h3 className="flex items-center gap-2 text-sm font-semibold"><Send className="size-4" />Prepared messages ({preview.data?.length ?? 0})</h3>
          <Button variant="ghost" asChild className="h-auto rounded-full px-3 text-xs"><Link to="/outbox">Open outbox</Link></Button>
        </div>
        <ul className="mt-3 grid gap-1.5 text-sm">{preview.data?.slice(0, 4).map(m => <li key={m.id} className="flex justify-between gap-3 rounded-xl bg-card px-3 py-2"><span className="truncate">{m.subject}</span><span className="truncate font-mono text-xs text-muted-foreground">{m.recipient}</span></li>)}{preview.data && preview.data.length > 4 && <li className="px-3 text-xs text-muted-foreground">and {preview.data.length - 4} more…</li>}</ul>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <div className="flex rounded-full bg-card p-1">{MODES.map(m => <button key={m.value} onClick={() => setMode(m.value)} className={`rounded-full px-4 py-1.5 text-xs font-medium transition-colors ${mode === m.value ? 'bg-forest text-forest-foreground' : 'text-muted-foreground hover:text-foreground'}`}>{m.label}</button>)}</div>
          {mode === 'live' && <label className="flex items-center gap-2 text-xs text-muted-foreground"><input type="checkbox" checked={confirmLive} onChange={e => setConfirmLive(e.target.checked)} className="size-4" />I confirm real sending to true recipients</label>}
          <Button disabled={execute.isPending || (mode === 'live' && !confirmLive)} onClick={() => execute.mutate()} className="ml-auto h-9 rounded-full bg-forest px-4 text-xs text-forest-foreground">{execute.isPending ? <><Loader2 className="size-4 animate-spin" />Running…</> : `Run ${mode}`}</Button>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">{modeHint}.</p>
      </div>}
    </section>}
  </div>;
}
