import { useState } from 'react';
import { Search, ListFilter } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { createFileRoute } from '@tanstack/react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { PageHeading, pageHead } from '@/components/ops/Workspace';
import { ExceptionCard } from '@/components/ops/ExceptionCard';
import { filterExceptions, type ExceptionFilter } from '@/lib/exception-details';
import { toast } from 'sonner';

export const Route = createFileRoute('/exceptions')({ head: () => pageHead('Exceptions', 'Resolve records that need a human decision before a workflow continues.'), component: ExceptionsPage });

function ExceptionsPage() {
  const [filter, setFilter] = useState<ExceptionFilter>('all');
  const [search, setSearch] = useState('');
  const qc = useQueryClient();
  const { data = [], isPending, isError } = useQuery({ queryKey: ['exceptions'], queryFn: () => api.getExceptions() });
  const resolve = useMutation({ mutationFn: ({ id, status }: { id: string; status: 'fixed' | 'rejected' }) => api.resolveException(id, status), onSuccess: () => qc.invalidateQueries(), onError: () => toast.error('Could not update this exception. Please try again.') });
  const visible = filterExceptions(data, filter, search);
  const filters: ExceptionFilter[] = ['all', 'open', 'fixed', 'rejected'];
  return <div><PageHeading title="Exceptions" subtitle="Records Igris won't act on without your decision." />
    <Tabs value={filter} onValueChange={value => { if (filters.includes(value as ExceptionFilter)) setFilter(value as ExceptionFilter); }}>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-border pb-5">
        <TabsList aria-label="Exception status" className="h-auto max-w-full justify-start gap-1 rounded-full bg-card p-1.5 shadow-dashboard">
          {filters.map(status => <TabsTrigger key={status} value={status} className="gap-1.5 rounded-full px-2.5 py-2 capitalize data-[state=active]:bg-forest data-[state=active]:text-forest-foreground sm:gap-2 sm:px-4">{status}<span className="rounded-full bg-current/10 px-1.5 text-[11px] tabular-nums">{status === 'all' ? data.length : data.filter(item => item.status === status).length}</span></TabsTrigger>)}
        </TabsList>
        <div className="relative w-full sm:w-72"><Search aria-hidden="true" className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" /><Input type="search" aria-label="Search exceptions by ID or name" placeholder="Search by ID or name…" value={search} onChange={event => setSearch(event.target.value)} className="h-11 rounded-full bg-card pl-10" /></div>
      </div>
      <p aria-live="polite" className="mb-4 text-xs font-medium text-muted-foreground">{visible.length} {visible.length === 1 ? 'exception' : 'exceptions'}{filter !== 'all' ? ` · ${filter}` : ''}</p>
      <TabsContent value={filter}>
        {isPending ? <p role="status" className="py-12 text-center text-sm text-muted-foreground">Loading exceptions…</p> : isError ? <p role="alert" className="py-12 text-center text-sm text-danger">Exceptions could not be loaded. Please refresh and try again.</p> : visible.length ? <div className="grid gap-5 md:grid-cols-2">{visible.map(item => <ExceptionCard key={item.id} item={item} busy={resolve.isPending} onResolve={(id, status) => resolve.mutate({ id, status })} />)}</div> : <div className="flex flex-col items-center gap-3 py-16 text-center"><ListFilter className="size-7 text-muted-foreground" /><h2 className="font-semibold">No matching exceptions</h2><p className="text-sm text-muted-foreground">{search ? 'Try another ID or name.' : `No ${filter === 'all' ? '' : `${filter} `}exceptions right now.`}</p></div>}
      </TabsContent>
    </Tabs>
  </div>;
}
