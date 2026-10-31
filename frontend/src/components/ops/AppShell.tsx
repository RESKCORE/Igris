import { Link, useRouterState } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { LayoutGrid, Table2, ListChecks, AlertTriangle, Send, ScrollText } from "lucide-react";
import { useOps } from "@/lib/mode-store";
import { cn } from "@/lib/utils";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutGrid },
  { to: "/data", label: "Data", icon: Table2 },
  { to: "/plan", label: "Plan", icon: ListChecks },
  { to: "/exceptions", label: "Exceptions", icon: AlertTriangle },
  { to: "/outbox", label: "Outbox", icon: Send },
  { to: "/audit", label: "Audit", icon: ScrollText },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const path = useRouterState({ select: (s) => s.location.pathname });
  const reducedMotion = useReducedMotion();
  const { runId } = useOps();
  return (
    <div className="min-h-screen p-3 pb-24 md:p-8 md:pb-8">
      <div className="mx-auto max-w-7xl rounded-[2rem] bg-shell p-4 md:p-6">
        <header className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-full bg-forest text-forest-foreground font-bold">IG</div>
            <div>
              <p className="text-xl font-semibold leading-tight md:text-2xl">Igris</p>
              <p className="text-xs text-muted-foreground">{runId ? `Run ${runId}` : "No active run"}</p>
            </div>
          </div>
          <nav className="hidden items-center gap-1 lg:flex">
            {nav.map((n) => (
              <Link key={n.to} to={n.to} className={cn("rounded-full px-4 py-2 text-sm transition-colors", path === n.to ? "bg-lime font-medium text-lime-foreground" : "text-muted-foreground hover:text-foreground")}>
                {n.label}
              </Link>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <Link to="/profile" aria-label="Admin profile" title="Admin profile" className="flex size-10 items-center justify-center rounded-full bg-lime text-sm font-semibold text-lime-foreground ring-offset-shell focus-visible:ring-2 focus-visible:ring-ring">SK</Link>
          </div>
        </header>

        <motion.main
          key={path}
          initial={reducedMotion || path === '/' ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: reducedMotion ? 0 : 0.35, ease: 'easeOut' }}
          className="mt-5 min-w-0"
        >{children}</motion.main>
      </div>

      <nav className="fixed inset-x-3 bottom-3 z-50 flex justify-around rounded-full bg-card p-2 shadow-lg lg:hidden">
        {nav.map((n) => (
          <Link key={n.to} to={n.to} aria-label={n.label} className={cn("flex size-11 items-center justify-center rounded-full", path === n.to ? "bg-lime text-lime-foreground" : "text-muted-foreground")}>
            <n.icon className="size-5" />
          </Link>
        ))}
      </nav>
    </div>
  );
}

export function RiskBadge({ risk }: { risk: "read" | "internal_write" | "external" }) {
  const map = {
    read: ["Read", "bg-muted text-muted-foreground"],
    internal_write: ["Internal write", "bg-info-soft text-info"],
    external: ["External", "bg-external-soft text-external"],
  } as const;
  const [l, c] = map[risk];
  return <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", c)}>{l}</span>;
}

export function StateChip({ state }: { state: string }) {
  return <span className="rounded-full bg-lime-soft px-2.5 py-0.5 text-xs font-medium capitalize text-lime-foreground">{state}</span>;
}

export function Placeholder({ title, note }: { title: string; note: string }) {
  return (
    <div className="panel flex min-h-[50vh] flex-col items-center justify-center text-center">
      <h1 className="text-3xl font-semibold">{title}</h1>
      <p className="mt-2 max-w-md text-muted-foreground">{note}</p>
    </div>
  );
}
