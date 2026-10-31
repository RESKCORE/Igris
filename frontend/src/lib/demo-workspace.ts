import type { ExceptionItem, OutboxMessage, Plan, Run, Task } from './types';

export const demoRuns: Run[] = [
  { id: 'run-demo-1', instruction: 'Email every customer whose invoice is more than 15 days overdue and log it in the tracker.', datasetId: 'invoices', mode: 'simulation', state: 'planned', createdAt: '2026-10-31T05:45:00Z' },
  { id: 'run-demo-2', instruction: "Send reminders for tomorrow's bookings and flag double-booked slots.", datasetId: 'bookings', mode: 'simulation', state: 'approved', createdAt: '2026-10-31T04:30:00Z' },
  { id: 'run-demo-3', instruction: 'Check new form submissions, add valid ones to the orders sheet, and notify the warehouse.', datasetId: 'orders', mode: 'simulation', state: 'executed', createdAt: '2026-10-30T12:15:00Z' },
];
export function demoPlans(builder: (instruction: string) => Task[]): Map<string, Plan> {
  return new Map(demoRuns.map(run => [run.id, { runId: run.id, version: 1, instruction: run.instruction, tasks: builder(run.instruction), approved: run.state !== 'planned' }]));
}
export const demoExceptions: ExceptionItem[] = [
  { id: 'ex-demo-1', runId: 'run-demo-1', taskId: 't2', rowRef: 'INV-106', reason: 'Amount is negative', rawData: { invoice_id: 'INV-106', customer: 'Priya Nair', amount: -120 }, suggestedFix: 'Review the credit note and confirm the amount.', status: 'open' },
  { id: 'ex-demo-2', runId: 'run-demo-1', taskId: 't2', rowRef: 'INV-112', reason: 'Customer does not exist', rawData: { invoice_id: 'INV-112', customer_id: 'C-099', amount: 407 }, suggestedFix: 'Match this invoice to an existing customer.', status: 'open' },
  { id: 'ex-demo-3', runId: 'run-demo-2', taskId: 't2', rowRef: 'BK-204', reason: 'Overlaps with BK-202', rawData: { booking_id: 'BK-204', resource: 'Pottery wheel', time: '10:00' }, suggestedFix: 'Move one booking to the next available slot.', status: 'open' },
  { id: 'ex-demo-4', runId: 'run-demo-1', taskId: 't2', rowRef: 'C-001', reason: 'Email looks malformed', rawData: { customer: 'Ravi Sharma', email: 'ravi@@example' }, suggestedFix: 'ravi@example.com', status: 'fixed' },
];
export const demoMessages: OutboxMessage[] = [
  { id: 'msg-demo-1', channel: 'email', recipient: 'anita@example.com', subject: 'Friendly payment reminder · INV-102', body: 'Hi Anita,\n\nA friendly reminder that your invoice INV-102 for $337 is overdue. Please let us know when we can expect payment, or if you have any questions.\n\nThank you,\nThe Igris team', mode: 'simulation', status: 'simulated', createdAt: '2026-10-31T05:50:00Z' },
  { id: 'msg-demo-2', channel: 'email', recipient: 'lena@example.com', subject: 'Your booking tomorrow · BK-204', body: 'Hi Lena,\n\nWe look forward to seeing you tomorrow for your pottery session. Your booking is at 10:00.\n\nThank you,\nThe Igris team', mode: 'simulation', status: 'simulated', createdAt: '2026-10-31T04:35:00Z' },
  { id: 'msg-demo-3', channel: 'message', recipient: 'warehouse@example.com', subject: 'New orders ready for review', body: 'The latest form submissions have been checked. Ten orders are ready for your review in the Orders dataset.', mode: 'simulation', status: 'simulated', createdAt: '2026-10-30T12:20:00Z' },
];