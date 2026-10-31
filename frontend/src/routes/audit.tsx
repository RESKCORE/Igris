import { Button } from '@/components/ui/button';
import { createFileRoute } from '@tanstack/react-router';
import { useMutation, useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { PageHeading, downloadFile, pageHead } from '@/components/ops/Workspace';

export const Route = createFileRoute('/audit')({ head: () => pageHead('Audit', 'See a tamper-evident timeline of every workflow action.'), component: AuditPage });

function AuditPage() {
  const { data = [] } = useQuery({ queryKey: ['audit'], queryFn: () => api.getAudit() });
  const verify = useMutation({ mutationFn: () => api.verifyAudit(), onSuccess: r => r.valid ? toast.success('Audit trail verified') : toast.error('Audit trail changed') });
  const exp = useMutation({ mutationFn: () => api.exportAudit(), onSuccess: s => downloadFile('igris-audit.json', s) });
  return <div><PageHeading title="Audit" subtitle="Every action is linked to the one before it."><div className="flex gap-2"><Button onClick={() => verify.mutate()} className="rounded-full bg-forest px-4 py-2 text-sm text-forest-foreground">Verify</Button><Button onClick={() => exp.mutate()} className="rounded-full border bg-card px-4 py-2 text-sm">Export</Button></div></PageHeading>
    <section className="panel"><ol className="space-y-3">{[...data].reverse().map(e => <li key={e.id} className="grid gap-2 rounded-2xl bg-muted p-4 md:grid-cols-[180px_1fr_auto]"><span className="text-xs text-muted-foreground">{new Date(e.ts).toLocaleString()}</span><span><span className="font-medium capitalize">{e.eventType.replaceAll('_', ' ')}</span><span className="block font-mono text-xs text-muted-foreground">{JSON.stringify(e.payload)}</span></span><span className="font-mono text-xs text-muted-foreground">#{e.hash.slice(0, 10)}</span></li>)}</ol></section></div>;
}
