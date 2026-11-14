/** Human labels and badge tones for enum codes. Never show raw codes in the UI. */
export type Tone = 'neutral' | 'info' | 'ok' | 'warn' | 'danger' | 'purple';

const STATUS: Record<string, { label: string; tone: Tone }> = {
  DRAFT: { label: 'Draft', tone: 'neutral' },
  SUBMITTED: { label: 'Submitted', tone: 'info' },
  ACCEPTED: { label: 'Accepted', tone: 'info' },
  REJECTED: { label: 'Rejected', tone: 'danger' },
  PENDING: { label: 'Pending', tone: 'warn' },
  IN_PROGRESS: { label: 'In progress', tone: 'purple' },
  AWAITING_VERIFICATION: { label: 'Awaiting verification', tone: 'warn' },
  VERIFIED: { label: 'Verified', tone: 'ok' },
  CLOSED: { label: 'Closed', tone: 'neutral' },
};

const TYPES: Record<string, string> = { BUG: 'Bug', CHANGE: 'Change', FEATURE: 'Feature', SUPPORT: 'Support' };
const PRIORITIES: Record<string, string> = { LOW: 'Low', MEDIUM: 'Medium', HIGH: 'High', CRITICAL: 'Critical' };

export const STATUS_CODES = Object.keys(STATUS);
export const TYPE_CODES = Object.keys(TYPES);
export const PRIORITY_CODES = Object.keys(PRIORITIES);

/** Fallback turns `SOME_CODE` into `Some code` so unknown values still read well. */
export function humanize(code: string): string {
  const text = code.replaceAll('_', ' ').trim().toLowerCase();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : '';
}

export const statusLabel = (code: string) => STATUS[code]?.label ?? humanize(code);
export const statusTone = (code: string): Tone => STATUS[code]?.tone ?? 'neutral';
export const typeLabel = (code: string | undefined | null) => (code ? (TYPES[code] ?? humanize(code)) : 'Type pending');
export const priorityLabel = (code: string | undefined | null) =>
  code ? (PRIORITIES[code] ?? humanize(code)) : 'Priority pending';

const EVENT_KINDS: Record<string, string> = {
  CREATED: 'Draft created',
  SUBMITTED: 'Submitted',
  ACCEPTED: 'Accepted',
  REJECTED: 'Rejected',
  TENTATIVE_DATE_REVISED: 'Tentative date revised',
  ASSIGNED: 'Assigned',
  REASSIGNED: 'Reassigned',
  STARTED: 'Work started',
  DELIVERED: 'Delivered',
  VERIFIED: 'Verified',
  VERIFICATION_FAILED: 'Verification failed',
  CLOSED: 'Closed',
  REOPENED: 'Reopened',
};

export const eventLabel = (kind: string) => EVENT_KINDS[kind] ?? humanize(kind);
