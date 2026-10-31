export type Mode = "simulation" | "sandbox" | "live";
export type Risk = "read" | "internal_write" | "external";

export interface Issue {
  ruleId: string;
  field: string;
  value: unknown;
  severity: "error" | "warning";
  message: string;
  suggestedFix?: string | undefined;
}
export interface Row {
  id: string;
  data: any;
  validationStatus: "ok" | "warning" | "error";
  issues: Issue[];
}
export interface Dataset {
  id: string;
  name: string;
  columns: string[];
  rows: Row[];
}
export interface Task {
  id: string;
  action: string;
  description: string;
  params: Record<string, any>;
  dependsOn: string[];
  risk: Risk;
  status: string;
}
export interface Plan {
  runId: string;
  version: number;
  instruction: string;
  tasks: Task[];
  clarifyingQuestion?: string;
  approved: boolean;
}
export interface Run {
  id: string;
  instruction: string;
  datasetId: string;
  mode: Mode;
  state: string;
  createdAt: string;
}
export interface ExceptionItem {
  id: string;
  runId: string;
  taskId: string;
  rowRef: string;
  reason: string;
  rawData: Record<string, any>;
  suggestedFix?: string | undefined;
  status: "open" | "approved" | "fixed" | "rejected";
}
export interface OutboxMessage {
  id: string;
  channel: "email" | "message";
  recipient: string;
  originalRecipient?: string;
  subject: string;
  body: string;
  mode: Mode;
  status: "simulated" | "sandbox" | "sent" | "failed";
  createdAt: string;
}
export interface AuditEvent {
  id: string;
  ts: string;
  actor: string;
  eventType: string;
  taskId?: string | undefined;
  payload: Record<string, any>;
  prevHash: string;
  hash: string;
}
