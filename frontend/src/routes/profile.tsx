import { Button } from '@/components/ui/button';
import { createFileRoute } from '@tanstack/react-router';
import { useState } from 'react';
import { toast } from 'sonner';
import { Mail, ShieldCheck, Building2, Clock } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { PageHeading, pageHead } from '@/components/ops/Workspace';

export const Route = createFileRoute('/profile')({ head: () => pageHead('Admin profile', 'Manage the Igris administrator profile and workspace preferences.'), component: ProfilePage });

function ProfilePage() {
  const [name, setName] = useState('Santosh Kumar'); const [email, setEmail] = useState('santosh@igris.app');
  return <div><PageHeading title="Admin profile" subtitle="Your sample workspace account." />
    <div className="grid gap-5 lg:grid-cols-[.8fr_1.2fr]"><section className="panel bg-lime"><div className="flex size-24 items-center justify-center rounded-full bg-forest text-3xl font-semibold text-forest-foreground">SK</div><h2 className="mt-5 text-2xl font-semibold text-lime-foreground">{name}</h2><p className="text-lime-foreground">Workspace administrator</p>
      <div className="mt-6 space-y-3 text-sm text-lime-foreground">{[[Mail, email], [Building2, 'Northwind Studio'], [ShieldCheck, 'Full approval access'], [Clock, 'Asia/Kolkata']].map(([I, v]: any) => <p key={v} className="flex items-center gap-2"><I className="size-4" />{v}</p>)}</div></section>
      <form className="panel grid content-start gap-4" onSubmit={e => { e.preventDefault(); toast.success('Profile updated'); }}><h2 className="text-lg font-medium">Profile details</h2><label className="grid gap-2 text-sm">Full name<Input value={name} onChange={e => setName(e.target.value)} className="rounded-full" /></label><label className="grid gap-2 text-sm">Email<Input type="email" value={email} onChange={e => setEmail(e.target.value)} className="rounded-full" /></label>
        <div className="grid grid-cols-3 gap-3 py-2 text-center">{[['24', 'Runs'], ['18', 'Approvals'], ['99%', 'Clean audits']].map(([v, l]) => <div key={l} className="rounded-2xl bg-muted p-3"><p className="text-xl font-semibold">{v}</p><p className="text-xs text-muted-foreground">{l}</p></div>)}</div><Button className="justify-self-start rounded-full bg-forest px-5 py-2.5 text-sm text-forest-foreground">Save changes</Button></form></div></div>;
}
