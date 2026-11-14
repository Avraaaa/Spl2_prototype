import { describe, expect, it } from 'vitest';
import { eventLines, eventTitle, type TimelineEvent } from './timeline';

const base: TimelineEvent = {
  kind: 'ASSIGNED',
  from_status: 'ACCEPTED',
  to_status: 'PENDING',
  reason: '',
  details: { to_assignee: 7 },
  actor_name: 'Sam Support',
  assignee_name: 'Priya Dev',
  created_at: '2026-11-01T10:00:00Z',
};

describe('timeline text', () => {
  it('shows names instead of ids', () => {
    const lines = eventLines(base).join(' ');
    expect(lines).toContain('Assigned to: Priya Dev');
    expect(lines).not.toContain('#7');
  });

  it('titles use human labels', () => {
    expect(eventTitle(base)).toBe('Assigned (Accepted → Pending)');
    expect(eventTitle({ ...base, kind: 'VERIFICATION_FAILED', from_status: 'AWAITING_VERIFICATION', to_status: 'IN_PROGRESS' })).toBe(
      'Verification failed (Awaiting verification → In progress)',
    );
  });

  it('includes reasons and date revisions', () => {
    const lines = eventLines({
      ...base,
      kind: 'TENTATIVE_DATE_REVISED',
      reason: 'Vendor delay',
      details: { from_date: '2026-11-10', to_date: '2026-11-20' },
    });
    expect(lines).toContain('Tentative delivery revised: 2026-11-10 → 2026-11-20');
    expect(lines).toContain('Reason: Vendor delay');
  });

  it('describes a deferred date', () => {
    expect(eventLines({ ...base, details: { tentative_delivery_later: true } })).toContain(
      'Tentative delivery: to be provided later',
    );
  });
});
