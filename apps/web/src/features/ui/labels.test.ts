import { describe, expect, it } from 'vitest';
import { eventLabel, humanize, priorityLabel, STATUS_CODES, statusLabel, statusTone, typeLabel } from './labels';

describe('human labels', () => {
  it('never shows raw status codes', () => {
    for (const code of STATUS_CODES) {
      expect(statusLabel(code)).not.toMatch(/_/);
      expect(statusLabel(code)).not.toBe(code);
    }
    expect(statusLabel('AWAITING_VERIFICATION')).toBe('Awaiting verification');
    expect(statusLabel('IN_PROGRESS')).toBe('In progress');
  });

  it('humanizes unknown codes', () => {
    expect(humanize('SOME_NEW_CODE')).toBe('Some new code');
    expect(statusLabel('WEIRD_STATE')).toBe('Weird state');
    expect(humanize('')).toBe('');
  });

  it('has a tone per status with a neutral fallback', () => {
    expect(statusTone('REJECTED')).toBe('danger');
    expect(statusTone('VERIFIED')).toBe('ok');
    expect(statusTone('NOPE')).toBe('neutral');
  });

  it('labels type, priority and events', () => {
    expect(typeLabel('BUG')).toBe('Bug');
    expect(typeLabel('')).toBe('Type pending');
    expect(priorityLabel('CRITICAL')).toBe('Critical');
    expect(priorityLabel(null)).toBe('Priority pending');
    expect(eventLabel('VERIFICATION_FAILED')).toBe('Verification failed');
    expect(eventLabel('SOMETHING_ELSE')).toBe('Something else');
  });
});
