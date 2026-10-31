import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { motion, MotionConfig, useReducedMotion, type Variants } from "framer-motion";
import { ArrowUpRight, Sparkles, Database, Inbox, Send, Loader2, RotateCcw, Download, MessageCircleQuestion, CheckCircle2, ListChecks, Workflow } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useOps } from "@/lib/mode-store";
import { StateChip } from "@/components/ops/AppShell";
import { getDashboardMetrics } from "@/lib/dashboard-metrics";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Dashboard · Igris" },
      { name: "description", content: "Tell Igris what you need done and review the plan before anything happens." },
      { property: "og:title", content: "Dashboard · Igris" },
      { property: "og:description", content: "Plain-language AI workflows with human approval and a full audit trail." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Dashboard,
});

const examples = [
  "Email every customer whose invoice is more than 15 days overdue and log it in the tracker.",
  "Check new form submissions, add valid ones to the orders sheet, and notify the warehouse.",
  "Send reminders for tomorrow's bookings and flag double-booked slots.",
];

const reveal: Variants = {
  hidden: { opacity: 0, y: 14 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
};
const stagger: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.07 } },
};

function Dashboard() {
  const reducedMotion = useReducedMotion();
  const qc = useQueryClient();
  const nav = useNavigate();
  const { setRunId } = useOps();
  const [text, setText] = useState("");
  const [ds, setDs] = useState("invoices");
  const [question, setQuestion] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");

  const datasets = useQuery({ queryKey: ["datasets"], queryFn: () => api.listDatasets() });
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api.listRuns() });
  const outbox = useQuery({ queryKey: ["outbox"], queryFn: () => api.getOutbox() });
  const exc = useQuery({ queryKey: ["exceptions"], queryFn: () => api.getExceptions() });

  const create = useMutation({
    mutationFn: (instr: string) => api.createRun(instr, ds),
    onSuccess: ({ run, plan }) => {
      qc.invalidateQueries();
      setRunId(run.id);
      if (plan.clarifyingQuestion) setQuestion(plan.clarifyingQuestion);
      else nav({ to: "/plan" });
    },
    onError: (e) => toast.error("Could not create plan", { description: e instanceof Error ? e.message : String(e) }),
  });
  const reset = useMutation({ mutationFn: () => api.resetDemoData(), onSuccess: () => { qc.invalidateQueries(); setRunId(null); toast.success("Demo data reset"); } });
  const load = useMutation({ mutationFn: () => api.loadDemoData(), onSuccess: () => { qc.invalidateQueries(); toast.success("Demo data loaded"); } });

  const rows = datasets.data?.flatMap((d) => d.rows) ?? [];
  const metrics = getDashboardMetrics(datasets.data ?? [], runs.data ?? []);
  const openEx = exc.data?.filter((e) => e.status === "open").length ?? 0;

  return (
    <MotionConfig reducedMotion="user">
    <motion.div initial={reducedMotion ? false : 'hidden'} animate="visible" variants={stagger} className="grid min-w-0 grid-cols-1 gap-5">
      <motion.header variants={reveal} className="flex flex-wrap items-end justify-between gap-3">
        <div><p className="mb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">Workspace overview</p><h1 className="text-3xl font-semibold">Dashboard</h1><p className="mt-1 text-sm text-muted-foreground">Your workflows, data, and decisions at a glance.</p></div>
        <span className="flex items-center gap-2 text-xs text-muted-foreground"><span className="size-2 rounded-full bg-success" />{datasets.data?.length ?? 0} datasets connected</span>
      </motion.header>
      <motion.div variants={stagger} className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Tile icon={Database} label="Total records" value={rows.length} detail={`${datasets.data?.length ?? 0} datasets`} />
        <Tile icon={CheckCircle2} label="Data quality" value={`${metrics.quality}%`} detail={`${metrics.valid} valid records`} />
        <Tile icon={Workflow} label="Total runs" value={runs.data?.length ?? 0} detail="Across all workflows" />
        <Tile icon={ListChecks} label="Completed runs" value={metrics.completed} detail="Execution finished" />
        <Tile icon={Inbox} label="Open exceptions" value={openEx} detail="Awaiting review" tone="text-danger" />
        <Tile icon={Send} label="Messages in outbox" value={outbox.data?.length ?? 0} detail="Prepared messages" />
      </motion.div>
      <motion.div variants={stagger} className="grid min-w-0 grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <motion.section variants={reveal} className="panel dashboard-surface min-w-0 shadow-dashboard transition-shadow duration-300 hover:shadow-dashboard-raised">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3"><span className="icon-bubble"><Sparkles className="size-4" /></span><h2 className="text-lg font-medium">What do you need done?</h2></div>
          </div>
          {question ? (
            <div className="mt-5 rounded-2xl bg-lime-soft p-5">
              <p className="flex items-center gap-2 font-medium text-lime-foreground"><MessageCircleQuestion className="size-5" />{question}</p>
              <Input className="mt-3 rounded-full bg-card" value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Your answer" />
              <Button className="mt-3 rounded-full" onClick={() => { setQuestion(null); create.mutate(`${text} — ${answer}`); }}>Continue</Button>
            </div>
          ) : (
            <>
              <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={4}
                placeholder="Tell me what you need done, e.g. Email every customer whose invoice is more than 15 days overdue and log it in the tracker."
                className="mt-5 resize-none rounded-2xl border-none bg-muted p-4 text-base" />
              <div className="mt-3 flex flex-wrap gap-2">
                {examples.map((e) => (
                  <Button variant="outline" key={e} onClick={() => setText(e)} className="h-auto whitespace-normal rounded-full bg-card px-3 py-1.5 text-left text-xs text-muted-foreground hover:border-forest hover:text-foreground">{e}</Button>
                ))}
              </div>
              <div className="mt-5 flex flex-wrap items-center gap-3">
                <Select value={ds} onValueChange={setDs}>
                  <SelectTrigger className="w-44 rounded-full"><SelectValue /></SelectTrigger>
                  <SelectContent>{datasets.data?.map((d) => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}</SelectContent>
                </Select>
                <Button disabled={!text.trim() || create.isPending} onClick={() => create.mutate(text)}
                  className="ml-auto h-10 rounded-full px-5 shadow-dashboard-action transition-all duration-200 motion-safe:hover:-translate-y-0.5 motion-safe:active:translate-y-0">
                  {create.isPending ? <><Loader2 className="size-4 animate-spin" />Planning your workflow...</> : "Create plan"}
                </Button>
              </div>
            </>
          )}
        </motion.section>

        <motion.section variants={reveal} whileHover={reducedMotion ? {} : { y: -3 }} className="panel dashboard-surface relative overflow-hidden bg-lime shadow-dashboard transition-shadow duration-300 hover:shadow-dashboard-raised">
          <Sparkles className="absolute -right-6 -top-6 size-48 text-lime-soft" strokeWidth={1} />
          <span className="relative inline-flex rounded-full bg-forest px-4 py-1.5 text-xs font-semibold tracking-wider text-forest-foreground">HUMAN APPROVED</span>
          <p className="relative mt-6 text-sm text-lime-foreground">Records in your workspace</p>
          <p className="relative text-5xl font-medium text-lime-foreground">{rows.length}</p>
          <div className="relative mt-6 grid grid-cols-2 gap-3">
            <div className="rounded-2xl bg-lime-soft p-4"><p className="text-xs text-lime-foreground">Load demo data</p>
               <Button variant="ghost" disabled={load.isPending} onClick={() => load.mutate()} className="mt-2 h-auto p-0 text-lime-foreground"><Download className="size-4" />Load</Button></div>
            <div className="rounded-2xl bg-lime-soft p-4"><p className="text-xs text-lime-foreground">Start over</p>
               <Button variant="ghost" disabled={reset.isPending} onClick={() => reset.mutate()} className="mt-2 h-auto p-0 text-lime-foreground"><RotateCcw className="size-4" />Reset</Button></div>
          </div>
        </motion.section>
      </motion.div>

      <motion.section variants={reveal} className="panel dashboard-surface min-w-0 shadow-dashboard transition-shadow duration-300 hover:shadow-dashboard-raised">
        <div className="flex items-center gap-3"><span className="icon-bubble"><ArrowUpRight className="size-4" /></span><h2 className="text-lg font-medium">Recent runs</h2></div>
        {runs.data?.length ? (
          <div className="mt-4 divide-y">
            {runs.data.map((r) => (
              <motion.div initial={false} whileHover={reducedMotion ? {} : { x: 3 }} key={r.id} className="flex flex-wrap items-center gap-3 py-3 transition-colors duration-200 hover:bg-muted/50">
                <p className="min-w-0 flex-1 truncate text-sm">{r.instruction}</p>
                <StateChip state={r.state} />
                <span className="text-xs capitalize text-muted-foreground">{r.mode}</span>
                <span className="text-xs text-muted-foreground">{new Date(r.createdAt).toLocaleTimeString()}</span>
                <Button variant="outline" size="sm" asChild className="rounded-full bg-card"><Link to="/plan" onClick={() => setRunId(r.id)}>Open<ArrowUpRight /></Link></Button>
              </motion.div>
            ))}
          </div>
        ) : <p className="mt-4 text-sm text-muted-foreground">No runs yet. Describe a task above to create your first plan.</p>}
      </motion.section>
    </motion.div>
    </MotionConfig>
  );
}

function Tile({ icon: Icon, label, value, detail, tone = "" }: { icon: any; label: string; value: number | string; detail: string; tone?: string }) {
  const reducedMotion = useReducedMotion();
  return (
    <motion.div variants={reveal} whileHover={reducedMotion ? {} : { y: -4 }} transition={{ type: 'spring', stiffness: 320, damping: 24 }} className="dashboard-surface min-w-0 rounded-2xl bg-card p-4 shadow-dashboard transition-shadow duration-300 hover:shadow-dashboard-raised">
      <span className="icon-bubble"><Icon className={`size-4 ${tone}`} /></span>
      <p className="mt-3 text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-3xl font-semibold tabular-nums">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
    </motion.div>
  );
}
