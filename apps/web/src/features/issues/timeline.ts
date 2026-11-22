import { formatDateTime } from '../ui/format';
import { eventLabel, statusLabel } from '../ui/labels';

export type TimelineEvent = {
  kind: string;
  from_status: string;
  to_status: string;
  reason?: string;
  details?: unknown;
  actor_name?: string;
  assignee_name?: string | null;
  created_at: string;
};

const LATER = 'to be provided later';

/** Human lines for one timeline event (dates, assignment, delivery). No raw IDs or codes. */
export function eventLines(event: TimelineEvent): string[] {
  const details = (event.details ?? {}) as Record<string, unknown>;
  const lines: string[] = [];
  if (details.tentative_delivery_date) lines.push(`Tentative delivery: ${String(details.tentative_delivery_date)}`);
  if (details.tentative_delivery_later === true) lines.push(`Tentative delivery: ${LATER}`);
  if (details.to_date) lines.push(`Tentative delivery revised: ${String(details.from_date ?? 'later')} → ${String(details.to_date)}`);
  if (details.to_later === true) lines.push(`Tentative delivery revised: ${String(details.from_date ?? 'later')} → ${LATER}`);
  if (details.actual_delivery_at) lines.push(`Actual delivery: ${formatDateTime(String(details.actual_delivery_at))}`);
  if (details.delivery_note) lines.push(`Delivery: ${String(details.delivery_note)}`);
  if (details.deployment_details) lines.push(`Version/deployment: ${String(details.deployment_details)}`);
  if (details.to_assignee && event.assignee_name) lines.push(`Assigned to: ${event.assignee_name}`);
  if (details.comment) lines.push(`Comment: ${String(details.comment)}`);
  if (event.reason) lines.push(`Reason: ${event.reason}`);
  return lines;
}

export function eventTitle(event: TimelineEvent): string {
  const move =
    event.from_status && event.to_status && event.from_status !== event.to_status
      ? ` (${statusLabel(event.from_status)} → ${statusLabel(event.to_status)})`
      : '';
  return `${eventLabel(event.kind)}${move}`;
}
