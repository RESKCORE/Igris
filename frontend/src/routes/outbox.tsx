import { Button } from '@/components/ui/button';
import { createFileRoute } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Mail, MessageSquare } from 'lucide-react';
import { api } from '@/lib/api';
import { PageHeading, Status, pageHead } from '@/components/ops/Workspace';
import { cn } from '@/lib/utils';

export const Route = createFileRoute('/outbox')({ head: () => pageHead('Outbox', 'Preview every message prepared by your approved workflows.'), component: OutboxPage });

function OutboxPage() {
  const { data = [] } = useQuery({ queryKey: ['outbox'], queryFn: () => api.getOutbox() });
  const [sel, setSel] = useState<string>(); const msg = data.find(m => m.id === sel) ?? data[0];
  return <div><PageHeading title="Outbox" subtitle="Prepared messages, kept safely in practice mode." />
    <div className="grid gap-5 lg:grid-cols-[.9fr_1.1fr]"><section className="panel space-y-2">{data.map(m => { const Icon = m.channel === 'email' ? Mail : MessageSquare; return <Button variant="ghost" key={m.id} onClick={() => setSel(m.id)} className={cn('flex h-auto w-full gap-3 rounded-2xl p-3 text-left', msg?.id === m.id ? 'bg-lime-soft' : 'hover:bg-muted')}><span className="icon-bubble shrink-0"><Icon className="size-4" /></span><span className="min-w-0 flex-1"><span className="block truncate font-medium">{m.subject}</span><span className="block truncate text-xs text-muted-foreground">{m.recipient}</span></span></Button>; })}</section>
      {msg && <article className="panel"><div className="flex justify-between gap-3"><div><p className="text-sm text-muted-foreground">To {msg.recipient}</p><h2 className="mt-1 text-xl font-medium">{msg.subject}</h2></div><Status value={msg.status} /></div><p className="mt-6 whitespace-pre-line rounded-2xl bg-muted p-5 text-sm leading-6">{msg.body}</p><p className="mt-4 text-xs text-muted-foreground">Prepared {new Date(msg.createdAt).toLocaleString()}</p></article>}</div></div>;
}
