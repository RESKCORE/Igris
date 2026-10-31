import type {
  AuditEvent, Dataset, ExceptionItem, Issue, Mode, OutboxMessage, Plan, Row, Run, Task,
} from "./types";
import { demoRuns, demoPlans, demoExceptions, demoMessages } from './demo-workspace';

export interface OpsApi {
  listDatasets(): Promise<Dataset[]>;
  getDatasetRows(id: string): Promise<Row[]>;
  updateRow(datasetId: string, rowId: string, data: Record<string, any>): Promise<Row>;
  loadDemoData(): Promise<void>;
  resetDemoData(): Promise<void>;
  createRun(instruction: string, datasetId: string): Promise<{ run: Run; plan: Plan }>;
  listRuns(): Promise<Run[]>;
  getRun(id: string): Promise<{ run: Run; plan: Plan } | null>;
  updatePlan(runId: string, tasks: Task[]): Promise<Plan>;
  approvePlan(runId: string): Promise<Plan>;
  getValidation(): Promise<{ passed: number; warnings: number; errors: number }>;
  getExceptions(runId?: string): Promise<ExceptionItem[]>;
  resolveException(id: string, status: ExceptionItem["status"], comment?: string): Promise<ExceptionItem>;
  getPreview(runId: string): Promise<OutboxMessage[]>;
  execute(runId: string, mode: Mode, confirm: boolean): Promise<OutboxMessage[]>;
  sendToSheets(datasetId: string): Promise<{ url: string; title: string; rowsWritten: number }>;
  getOutbox(): Promise<OutboxMessage[]>;
  getAudit(): Promise<AuditEvent[]>;
  verifyAudit(): Promise<{ valid: boolean }>;
  exportAudit(): Promise<string>;
}

/* ---------------- seed ---------------- */
const uid = (p: string, n: number) => `${p}-${String(n).padStart(3, "0")}`;
const daysAgo = (d: number) => new Date(Date.now() - d * 864e5).toISOString().slice(0, 10);

function seed(): Dataset[] {
  const names = ["Ravi Sharma","Anita Desai","Tom Becker","Lena Park","Omar Haddad","Priya Nair","Sam Ortiz","Mia Chen","Jonas Weber","Aisha Bello","Leo Rossi","Nora Kim"];
  const customers: any[] = names.map((n, i) => ({
    customer_id: uid("C", i + 1),
    name: n,
    email: i === 0 ? "ravi@@example" : i === 4 ? "" : `${n.split(" ")[0]!.toLowerCase()}@example.com`,
    phone: `+1 555 01${String(i).padStart(2, "0")}`,
    city: ["Austin","Denver","Portland","Boston"][i % 4],
  }));
  const invoices: any[] = Array.from({ length: 15 }, (_, i) => ({
    invoice_id: i === 7 ? "INV-103" : `INV-${101 + i}`,
    customer_id: i === 11 ? "C-099" : uid("C", (i % 12) + 1),
    amount: i === 5 ? -120 : i === 9 ? 4800 : 300 + ((i * 37) % 200),
    due_date: i === 13 ? "2099-01-01" : daysAgo(5 + i * 3),
    status: i % 3 === 0 ? "paid" : "unpaid",
  }));
  const orders: any[] = Array.from({ length: 10 }, (_, i) => ({
    order_id: `ORD-${501 + i}`,
    customer_id: uid("C", (i % 12) + 1),
    item: ["Ceramic mug","Linen tote","Candle set","Notebook","Tea tin"][i % 5],
    qty: 1 + (i % 4),
    total: 18 + i * 6,
  }));
  const bookings: any[] = Array.from({ length: 10 }, (_, i) => ({
    booking_id: `BK-${201 + i}`,
    customer_id: uid("C", (i % 12) + 1),
    resource: ["Workshop room","Pottery wheel"][i % 2],
    date: daysAgo(-1 - (i % 3)),
    time: i === 3 ? "10:00" : `${9 + i}:00`,
  }));
  // overlapping booking: BK-202 vs BK-204 same resource/date/time
  bookings[3].resource = bookings[1].resource;
  bookings[3].date = bookings[1].date;
  bookings[3].time = bookings[1].time;

  const wrap = (p: string, arr: any[]): Row[] =>
    arr.map((d, i) => ({ id: uid(p, i + 1), data: d, validationStatus: "ok", issues: [] }));
  const ds: Dataset[] = [
    { id: "customers", name: "Customers", columns: Object.keys(customers[0]), rows: wrap("r-c", customers) },
    { id: "invoices", name: "Invoices", columns: Object.keys(invoices[0]), rows: wrap("r-i", invoices) },
    { id: "orders", name: "Orders", columns: Object.keys(orders[0]), rows: wrap("r-o", orders) },
    { id: "bookings", name: "Bookings", columns: Object.keys(bookings[0]), rows: wrap("r-b", bookings) },
  ];
  validateAll(ds);
  return ds;
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export function validateAll(ds: Dataset[]) {
  const custIds = new Set(ds.find((d) => d.id === "customers")!.rows.map((r) => r.data.customer_id));
  for (const d of ds) {
    const seen = new Map<string, number>();
    const key = d.columns[0]!;
    d.rows.forEach((r) => seen.set(r.data[key], (seen.get(r.data[key]) ?? 0) + 1));
    const amounts = d.rows.map((r) => Number(r.data.amount)).filter((n) => n > 0).sort((a, b) => a - b);
    const median = amounts[Math.floor(amounts.length / 2)] ?? 0;
    for (const r of d.rows) {
      const issues: Issue[] = [];
      const v = r.data;
      if ("email" in v) {
        if (!v.email) issues.push({ ruleId: "R-REQ", field: "email", value: v.email, severity: "error", message: "Email is missing" });
        else if (!EMAIL.test(v.email)) issues.push({ ruleId: "R-EMAIL", field: "email", value: v.email, severity: "error", message: "Email looks malformed", suggestedFix: String(v.email).replace("@@", "@") + (String(v.email).includes(".") ? "" : ".com") });
      }
      if ((seen.get(v[key]) ?? 0) > 1) issues.push({ ruleId: "R-DUP", field: key, value: v[key], severity: "error", message: `Duplicate ${key}` });
      if ("amount" in v) {
        const a = Number(v.amount);
        if (a < 0) issues.push({ ruleId: "R-NEG", field: "amount", value: a, severity: "error", message: "Amount is negative", suggestedFix: String(Math.abs(a)) });
        else if (median && a > median * 8) issues.push({ ruleId: "R-OUTLIER", field: "amount", value: a, severity: "warning", message: "Amount is about 10x the usual" });
      }
      for (const f of ["due_date", "date"]) {
        if (f in v && Number(String(v[f]).slice(0, 4)) > 2030) issues.push({ ruleId: "R-DATE", field: f, value: v[f], severity: "warning", message: "Date looks unrealistic" });
      }
      if (d.id !== "customers" && "customer_id" in v && !custIds.has(v.customer_id)) issues.push({ ruleId: "R-REF", field: "customer_id", value: v.customer_id, severity: "error", message: "Customer does not exist" });
      if (d.id === "bookings") {
        const clash = d.rows.find((o) => o !== r && o.data.resource === v.resource && o.data.date === v.date && o.data.time === v.time);
        if (clash) issues.push({ ruleId: "R-OVERLAP", field: "time", value: v.time, severity: "error", message: `Overlaps with ${clash.data.booking_id}` });
      }
      r.issues = issues;
      r.validationStatus = issues.some((i) => i.severity === "error") ? "error" : issues.length ? "warning" : "ok";
    }
  }
}

/* ---------------- plans ---------------- */
const t = (n: number, action: string, description: string, risk: Task["risk"], params: Record<string, any> = {}): Task => ({
  id: `t${n}`, action, description, risk, params, dependsOn: n > 1 ? [`t${n - 1}`] : [], status: "pending",
});
function planFor(instruction: string): Task[] {
  const s = instruction.toLowerCase();
  if (s.includes("overdue"))
    return [
      t(1, "read_dataset", "Read the Invoices data", "read", { dataset: "invoices" }),
      t(2, "filter_rows", "Find invoices more than 15 days overdue", "read", { days_overdue: 15 }),
      t(3, "draft_messages", "Write a payment reminder for each customer", "internal_write", { template: "Payment reminder" }),
      t(4, "send_email", "Send each reminder by email", "external", { channel: "email" }),
      t(5, "update_rows", 'Mark each invoice as "Reminded" in the tracker', "internal_write", { status: "Reminded" }),
    ];
  if (s.includes("form submission"))
    return [
      t(1, "read_submissions", "Check new form submissions", "read"),
      t(2, "validate_rows", "Keep only valid submissions", "read"),
      t(3, "append_rows", "Add valid ones to the Orders sheet", "internal_write", { dataset: "orders" }),
      t(4, "send_message", "Notify the warehouse", "external", { channel: "message", recipient: "warehouse" }),
    ];
  if (s.includes("booking"))
    return [
      t(1, "read_dataset", "Read tomorrow's bookings", "read", { dataset: "bookings" }),
      t(2, "detect_overlaps", "Flag double-booked slots", "read"),
      t(3, "draft_messages", "Write a reminder for each booking", "internal_write", { template: "Booking reminder" }),
      t(4, "send_email", "Send reminders by email", "external", { channel: "email" }),
    ];
  return [
    t(1, "read_dataset", "Read the selected data", "read"),
    t(2, "analyze", "Work out what needs doing", "read"),
    t(3, "write_summary", "Save a summary for your review", "internal_write"),
  ];
}

/* ---------------- mock ---------------- */
const wait = (ms = 250) => new Promise((r) => setTimeout(r, ms));
async function sha(s: string) {
  const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return Array.from(new Uint8Array(b)).map((x) => x.toString(16).padStart(2, "0")).join("").slice(0, 16);
}

function createMock(): OpsApi {
  let datasets = seed();
  const runs: Run[] = structuredClone(demoRuns);
  const plans = demoPlans(planFor);
  let exceptions: ExceptionItem[] = structuredClone(demoExceptions);
  const outbox: OutboxMessage[] = structuredClone(demoMessages);
  const audit: AuditEvent[] = [];
  let n = 0;

  async function log(eventType: string, payload: Record<string, any>, taskId?: string) {
    const prevHash = audit.at(-1)?.hash ?? "genesis";
    const ts = new Date().toISOString();
    const hash = await sha(prevHash + ts + eventType + JSON.stringify(payload));
    audit.push({ id: `ev-${audit.length + 1}`, ts, actor: "owner", eventType, taskId, payload, prevHash, hash });
  }

  const ready = (async () => {
    await log('demo_loaded', { datasets: datasets.length, records: datasets.flatMap(d => d.rows).length });
    await log('run_created', { runId: 'run-demo-1', dataset: 'invoices' });
    await log('validation_completed', { runId: 'run-demo-1', exceptions: 2 });
    await log('plan_approved', { runId: 'run-demo-2', approvedBy: 'Santosh Kumar' });
    await log('messages_simulated', { count: 3, externalDelivery: false });
  })();

  return {
    async listDatasets() { await wait(); return structuredClone(datasets); },
    async getDatasetRows(id) { await wait(); return structuredClone(datasets.find((d) => d.id === id)?.rows ?? []); },
    async updateRow(dsId, rowId, data) {
      await wait();
      const r = datasets.find((d) => d.id === dsId)!.rows.find((x) => x.id === rowId)!;
      r.data = { ...r.data, ...data };
      validateAll(datasets);
      await log("row_updated", { dsId, rowId, data });
      return structuredClone(r);
    },
    async loadDemoData() { await wait(); datasets = seed(); await log("demo_loaded", {}); },
    async resetDemoData() { await wait(); datasets = seed(); runs.length = 0; plans.clear(); exceptions = []; outbox.length = 0; await log("demo_reset", {}); },
    async createRun(instruction, datasetId) {
      await wait(1500);
      const id = `run-${++n}`;
      const run: Run = { id, instruction, datasetId, mode: "simulation", state: "planned", createdAt: new Date().toISOString() };
      const plan: Plan = { runId: id, version: 1, instruction, tasks: planFor(instruction), approved: false };
      if (instruction.trim().split(/\s+/).length < 4) plan.clarifyingQuestion = "Could you tell me a bit more? Which records and what should happen to them?";
      runs.unshift(run); plans.set(id, plan);
      const ds = datasets.find((d) => d.id === datasetId);
      exceptions.push(...(ds?.rows.filter((r) => r.validationStatus === "error").map((r) => ({
        id: `ex-${id}-${r.id}`, runId: id, taskId: "t2", rowRef: String(r.data[ds.columns[0]!]),
        reason: r.issues.map((i) => i.message).join("; "), rawData: r.data,
        suggestedFix: r.issues.find((i) => i.suggestedFix)?.suggestedFix, status: "open" as const,
      })) ?? []));
      await log("run_created", { id, instruction });
      return structuredClone({ run, plan });
    },
    async listRuns() { await wait(); return structuredClone(runs); },
    async getRun(id) { await wait(); const run = runs.find((r) => r.id === id); return run ? structuredClone({ run, plan: plans.get(id)! }) : null; },
    async updatePlan(runId, tasks) { await wait(); const p = plans.get(runId)!; p.tasks = tasks; p.version++; await log("plan_updated", { runId, version: p.version }); return structuredClone(p); },
    async approvePlan(runId) { await wait(); const p = plans.get(runId)!; p.approved = true; runs.find((r) => r.id === runId)!.state = "approved"; await log("plan_approved", { runId }); return structuredClone(p); },
    async getValidation() {
      await wait();
      const rows = datasets.flatMap((d) => d.rows);
      return { passed: rows.filter((r) => r.validationStatus === "ok").length, warnings: rows.filter((r) => r.validationStatus === "warning").length, errors: rows.filter((r) => r.validationStatus === "error").length };
    },
    async getExceptions(runId) { await wait(); return structuredClone(exceptions.filter((e) => !runId || e.runId === runId)); },
    async resolveException(id, status, comment) { await wait(); const e = exceptions.find((x) => x.id === id)!; e.status = status; await log("exception_resolved", { id, status, comment }); return structuredClone(e); },
    async getPreview(runId) {
      await wait();
      return [{ id: `pv-${runId}`, channel: "email", recipient: "anita@example.com", subject: "Friendly payment reminder", body: "Hi Anita, a quick reminder that invoice INV-102 is overdue.", mode: "simulation", status: "simulated", createdAt: new Date().toISOString() }];
    },
    async execute(runId, mode, confirm) {
      await wait(800);
      if (mode === "live" && !confirm) throw new Error("Live mode needs confirmation");
      const msgs = (await this.getPreview(runId)).map((m) => ({ ...m, id: `msg-${outbox.length + 1}`, mode, status: (mode === "live" ? "sent" : mode === "sandbox" ? "sandbox" : "simulated") as OutboxMessage["status"], ...(mode === "sandbox" ? { originalRecipient: m.recipient, recipient: "test@example.com" } : {}) }));
      outbox.unshift(...msgs);
      runs.find((r) => r.id === runId)!.state = "executed";
      await log("executed", { runId, mode, count: msgs.length });
      return structuredClone(msgs);
    },
    async getOutbox() { await wait(); return structuredClone(outbox); },
    async getAudit() { await ready; await wait(); return structuredClone(audit); },
    async verifyAudit() {
      await ready;
      await wait();
      let prev = "genesis";
      for (const e of audit) {
        if (e.prevHash !== prev || e.hash !== (await sha(prev + e.ts + e.eventType + JSON.stringify(e.payload)))) return { valid: false };
        prev = e.hash;
      }
      return { valid: true };
    },
    async exportAudit() { await ready; await wait(); return JSON.stringify(audit, null, 2); },
    async sendToSheets(datasetId) {
      await wait();
      const n = datasets.find((d) => d.id === datasetId)?.rows.length ?? 0;
      return { url: "https://sheets.example.com/demo", title: "Demo export", rowsWritten: n };
    },
  };
}

let _api: OpsApi | null = null;
const API_URL = ((import.meta.env as any).VITE_API_URL as string | undefined)?.replace(/\/+$/, "");

export function getApi(): OpsApi {
  // Real backend when VITE_API_URL is set; in-browser mock otherwise.
  if (!_api) _api = API_URL ? createRest(API_URL) : createMock();
  return _api;
}
export const api = new Proxy({} as OpsApi, { get: (_, k) => (getApi() as any)[k] });

/* ---------------- REST client (FastAPI backend) ---------------- */

function createRest(base: string): OpsApi {
  // Backend run states (/runs uses PLANNED / PLAN_APPROVED / COMPLETED) mapped to the
  // lowercase vocabulary the dashboard states are keyed on.
  const STATE_MAP: Record<string, string> = {
    CREATED: "planned",
    PLANNED: "planned",
    PLAN_APPROVED: "approved",
    READY_TO_EXECUTE: "approved",
    EXECUTING: "executed",
    COMPLETED: "executed",
  };

  const mapIssue = (i: any): Issue => ({
    ruleId: i.rule_id,
    field: i.field,
    value: i.value,
    severity: i.severity,
    message: i.message,
    suggestedFix: i.suggested_fix ?? undefined,
  });
  const mapRow = (r: any): Row => ({
    id: r.id,
    data: r.data ?? {},
    validationStatus: r.validation_status ?? "ok",
    issues: (r.issues ?? []).map(mapIssue),
  });
  const mapRun = (r: any): Run => ({
    id: r.id,
    instruction: r.instruction,
    datasetId: r.dataset_id ?? "",
    mode: r.mode,
    state: STATE_MAP[r.state] ?? String(r.state).toLowerCase(),
    createdAt: r.created_at,
  });
  const mapTask = (t: any): Task => ({
    id: t.id ?? "",
    action: t.action,
    description: t.description,
    params: t.params ?? {},
    dependsOn: t.depends_on ?? [],
    risk: t.risk ?? "read",
    status: t.status ?? "pending_review",
  });
  const mapPlan = (run: any, p: any | null): Plan => ({
    runId: p?.run_id ?? run.id,
    version: p?.version ?? 1,
    instruction: p?.instruction ?? run.instruction ?? "",
    tasks: (p?.tasks ?? []).map(mapTask),
    clarifyingQuestion: p?.clarifying_question ?? undefined,
    approved: Boolean(p?.approved ?? p?.approved_by),
  });
  const mapException = (e: any): ExceptionItem => ({
    id: e.id,
    runId: e.run_id,
    taskId: e.task_id ?? "",
    rowRef: e.row_ref ?? "",
    reason: e.reason,
    rawData: e.raw_data ?? {},
    suggestedFix: e.suggested_fix ?? undefined,
    status: e.status,
  });
  const mapMessage = (m: any): OutboxMessage => ({
    id: m.id,
    channel: m.channel === "email" ? "email" : "message",
    recipient: m.recipient,
    originalRecipient: m.original_recipient ?? undefined,
    subject: m.subject ?? "",
    body: m.body ?? "",
    mode: m.mode,
    status: m.status,
    createdAt: m.created_at,
  });
  const mapAudit = (e: any): AuditEvent => ({
    id: e.id,
    ts: e.ts,
    actor: e.actor,
    eventType: e.event_type,
    taskId: e.task_id ?? undefined,
    payload: e.payload ?? {},
    prevHash: e.prev_hash,
    hash: e.hash,
  });

  async function req(method: string, path: string, body?: unknown): Promise<any> {
    const init: RequestInit = body !== undefined
      ? { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
      : { method };
    const res = await fetch(`${base}${path}`, init);
    if (!res.ok) {
      let message = `${res.status} ${res.statusText}`;
      let code: string | undefined;
      try {
        const j = await res.json();
        if (j?.error?.message) message = j.error.message;
        code = j?.error?.code;
      } catch {
        /* non-JSON error body */
      }
      const err = new Error(message);
      (err as any).code = code;
      throw err;
    }
    const contentType = res.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) return res.text();
    const text = await res.text();
    return text ? JSON.parse(text) : undefined;
  }

  const toTaskPayload = (t: Task) => ({
    id: t.id,
    action: t.action,
    description: t.description,
    params: t.params,
    depends_on: t.dependsOn,
    risk: t.risk,
    status: t.status,
  });
  const planShape = (run: any, p: any): Plan => mapPlan(run, p);

  return {
    async listDatasets(): Promise<Dataset[]> {
      const list = await req("GET", "/datasets");
      const withRows = await Promise.all(
        (list ?? []).map(async (d: any) => {
          const rs = await req("GET", `/datasets/${d.id}/rows`);
          return { id: d.id, name: d.name, columns: d.schema?.columns ?? [], rows: (rs?.rows ?? []).map(mapRow) };
        }),
      );
      return withRows;
    },
    async getDatasetRows(id): Promise<Row[]> {
      const rs = await req("GET", `/datasets/${id}/rows`);
      return (rs?.rows ?? []).map(mapRow);
    },
    async updateRow(dsId, rowId, data): Promise<Row> {
      const r = await req("PATCH", `/datasets/${dsId}/rows/${rowId}`, { data });
      return mapRow(r);
    },
    async loadDemoData(): Promise<void> {
      await req("POST", "/datasets/demo/load");
    },
    async resetDemoData(): Promise<void> {
      await req("POST", "/datasets/demo/reset");
    },
    async createRun(instruction, datasetId): Promise<{ run: Run; plan: Plan }> {
      const body = await req("POST", "/runs", { instruction, dataset_id: datasetId || undefined });
      const src = body?.run ?? body;
      return { run: mapRun(src), plan: planShape(src, body.plan ?? body) };
    },
    async listRuns(): Promise<Run[]> {
      const list = await req("GET", "/runs");
      return (list ?? []).map(mapRun);
    },
    async getRun(id): Promise<{ run: Run; plan: Plan } | null> {
      try {
        const body = await req("GET", `/runs/${id}`);
        return { run: mapRun(body), plan: planShape(body, body.plan) };
      } catch (e: any) {
        if (e?.code === "run_not_found") return null;
        throw e;
      }
    },
    async updatePlan(runId, tasks): Promise<Plan> {
      const p = await req("PUT", `/runs/${runId}/plan`, { tasks: tasks.map(toTaskPayload) });
      return planShape({ id: p?.run_id }, p);
    },
    async approvePlan(runId): Promise<Plan> {
      const p = await req("POST", `/runs/${runId}/approve`);
      return planShape({ id: p?.run_id }, p);
    },
    async getValidation(): Promise<{ passed: number; warnings: number; errors: number }> {
      return req("GET", "/validation");
    },
    async getExceptions(runId): Promise<ExceptionItem[]> {
      const list = await req("GET", runId ? `/exceptions?run_id=${encodeURIComponent(runId)}` : "/exceptions");
      return (list ?? []).map(mapException);
    },
    async resolveException(id, status, comment): Promise<ExceptionItem> {
      const decision = status === "fixed" ? "fix" : status === "rejected" ? "reject" : "approve";
      const e = await req("POST", `/exceptions/${id}/resolve`, { decision, reason: comment });
      return mapException(e);
    },
    async getPreview(runId): Promise<OutboxMessage[]> {
      const list = await req("GET", `/runs/${runId}/preview`);
      return (list ?? []).map(mapMessage);
    },
    async execute(runId, mode, confirm): Promise<OutboxMessage[]> {
      const list = await req("POST", `/runs/${runId}/execute`, { mode, confirm });
      return (list ?? []).map(mapMessage);
    },
    async sendToSheets(datasetId): Promise<{ url: string; title: string; rowsWritten: number }> {
      const r = await req("POST", `/datasets/${encodeURIComponent(datasetId)}/sheets`);
      return { url: r.spreadsheet_url, title: r.spreadsheet_title, rowsWritten: r.rows_written };
    },
    async getOutbox(): Promise<OutboxMessage[]> {
      const list = await req("GET", "/outbox");
      return (list ?? []).map(mapMessage);
    },
    async getAudit(): Promise<AuditEvent[]> {
      const list = await req("GET", "/audit");
      return (list ?? []).map(mapAudit);
    },
    async verifyAudit(): Promise<{ valid: boolean }> {
      const r = await req("GET", "/audit/verify");
      return { valid: Boolean(r?.valid) };
    },
    async exportAudit(): Promise<string> {
      return req("GET", "/audit/export");
    },
  };
}
