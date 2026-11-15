import { formatDateTime } from '../ui/format';

type DeliveryEvent = {
  kind: string;
  details?: unknown;
};

type DeliveryRecord = {
  status?: string;
  actual_delivery_at?: string | null;
  events: readonly DeliveryEvent[];
};

function latestHistoricalDelivery(events: readonly DeliveryEvent[]): string | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (!event || event.kind !== 'DELIVERED') continue;
    const details = (event.details ?? {}) as Record<string, unknown>;
    if (typeof details.actual_delivery_at === 'string') return details.actual_delivery_at;
  }
  return null;
}

/** Describe current delivery state without hiding an earlier immutable delivery event. */
export function deliverySummary(issue: DeliveryRecord): string {
  if (issue.actual_delivery_at) return formatDateTime(issue.actual_delivery_at);

  const previousDelivery = latestHistoricalDelivery(issue.events);
  if (!previousDelivery) return 'Not delivered';

  const formatted = formatDateTime(previousDelivery);
  if (issue.status === 'IN_PROGRESS') {
    return `Awaiting redelivery; previous delivery: ${formatted}`;
  }
  return `Previous delivery: ${formatted}`;
}
