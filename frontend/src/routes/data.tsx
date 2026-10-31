import { Button } from '@/components/ui/button';
import { createFileRoute } from '@tanstack/react-router';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { toast } from 'sonner';
import { ExternalLink } from 'lucide-react';
import { api } from '@/lib/api';
import { Metrics, PageHeading, Status, pageHead } from '@/components/ops/Workspace';
import { cn } from '@/lib/utils';

export const Route = createFileRoute('/data')({ head: () => pageHead('Data', 'Review customers, invoices, orders and bookings with clear validation status.'), component: DataPage });

function DataPage() {
  const { data = [] } = useQuery({ queryKey: ['datasets'], queryFn: () => api.listDatasets() });
  const [active, setActive] = useState('invoices');
  const ds = data.find(d => d.id === active) ?? data[0];
  const rows = data.flatMap(d => d.rows);
  const sheets = useMutation({
    mutationFn: () => api.sendToSheets(ds!.id),
    onSuccess: (r) => { toast.success(r.title, { description: `${r.rowsWritten} rows written to Google Sheets`, action: <a href={r.url} target="_blank" rel="noreferrer" className="rounded-full bg-forest px-3 py-1 text-xs text-forest-foreground">Open sheet</a> }); },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Sheets export failed'),
  });
  return <div><PageHeading title="Data" subtitle="Sample business records, checked before any workflow runs." >
    {ds && <Button disabled={sheets.isPending} onClick={() => sheets.mutate()} className="rounded-full bg-forest px-4 py-2 text-sm text-forest-foreground">{sheets.isPending ? 'Sending to Sheets…' : (<><ExternalLink className="size-4" />Send to Sheets</>)}</Button>}
  </PageHeading>
    <Metrics items={[{ label: 'Total records', value: rows.length }, { label: 'Valid', value: rows.filter(r => r.validationStatus === 'ok').length }, { label: 'Warnings', value: rows.filter(r => r.validationStatus === 'warning').length }, { label: 'Errors', value: rows.filter(r => r.validationStatus === 'error').length }]} />
    <section className="panel"><div className="mb-5 flex flex-wrap gap-2">{data.map(d => <Button variant="ghost" key={d.id} onClick={() => setActive(d.id)} className={cn('rounded-full px-4 py-2 text-sm', ds?.id === d.id ? 'bg-forest text-forest-foreground' : 'bg-muted text-muted-foreground')}>{d.name} · {d.rows.length}</Button>)}</div>
      {ds && <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-sm"><thead><tr className="text-left text-muted-foreground">{ds.columns.map(c => <th key={c} className="px-3 py-3 font-medium capitalize">{c.replaceAll('_', ' ')}</th>)}<th className="px-3 py-3 font-medium">Status</th></tr></thead><tbody className="divide-y">{ds.rows.map(r => <tr key={r.id}>{ds.columns.map(c => <td key={c} className={cn('px-3 py-3', r.issues.some(i => i.field === c) && 'text-danger')}>{String(r.data[c] || '—')}</td>)}<td className="px-3 py-3"><Status value={r.validationStatus} />{r.issues[0] && <p className="mt-1 text-xs text-muted-foreground">{r.issues[0].message}</p>}</td></tr>)}</tbody></table></div>}
    </section></div>;
}
