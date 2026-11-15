import { describe, expect, it } from 'vitest';
import { formatDateTime } from '../ui/format';
import { deliverySummary } from './delivery';

const previousDelivery = '2026-11-12T08:30:00Z';

describe('delivery summary', () => {
  it('shows the current actual delivery when present', () => {
    expect(
      deliverySummary({
        status: 'AWAITING_VERIFICATION',
        actual_delivery_at: previousDelivery,
        events: [],
      }),
    ).toBe(formatDateTime(previousDelivery));
  });

  it('explains that an in-progress request is awaiting redelivery', () => {
    expect(
      deliverySummary({
        status: 'IN_PROGRESS',
        actual_delivery_at: null,
        events: [
          {
            kind: 'DELIVERED',
            details: { actual_delivery_at: previousDelivery },
          },
          {
            kind: 'VERIFICATION_FAILED',
            details: {},
          },
        ],
      }),
    ).toBe(`Awaiting redelivery; previous delivery: ${formatDateTime(previousDelivery)}`);
  });

  it('uses the latest historical delivery and handles requests never delivered', () => {
    const latestDelivery = '2026-11-15T10:00:00Z';
    expect(
      deliverySummary({
        status: 'IN_PROGRESS',
        actual_delivery_at: null,
        events: [
          { kind: 'DELIVERED', details: { actual_delivery_at: previousDelivery } },
          { kind: 'DELIVERED', details: { actual_delivery_at: latestDelivery } },
        ],
      }),
    ).toContain(formatDateTime(latestDelivery));

    expect(
      deliverySummary({
        status: 'SUBMITTED',
        actual_delivery_at: null,
        events: [],
      }),
    ).toBe('Not delivered');
  });
});
