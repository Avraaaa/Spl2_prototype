import { describe, expect, it } from 'vitest';
import { landingFor, roleLabel, hasRole } from './roles';

const user = (roles: Array<'ISSUE_OFFICER' | 'ISSUE_VERIFIER' | 'DATASOFT_ADMIN' | 'SUPPORT_AGENT'>, must = false) => ({
  roles,
  must_change_password: must,
});

describe('role helpers (UI hints only; Django enforces permissions)', () => {
  it('labels roles for display', () => {
    expect(roleLabel('ISSUE_VERIFIER')).toBe('Issue Verifier');
    expect(roleLabel('DATASOFT_ADMIN')).toBe('DataSoft Administrator');
  });

  it('detects dual Officer + Verifier roles', () => {
    const dual = user(['ISSUE_OFFICER', 'ISSUE_VERIFIER']);
    expect(hasRole(dual, 'ISSUE_OFFICER')).toBe(true);
    expect(hasRole(dual, 'ISSUE_VERIFIER')).toBe(true);
    expect(hasRole(dual, 'DATASOFT_ADMIN')).toBe(false);
  });

  it('routes users to the right landing page', () => {
    expect(landingFor(null)).toBe('/login');
    expect(landingFor(user(['ISSUE_OFFICER'], true))).toBe('/change-password');
    expect(landingFor(user(['DATASOFT_ADMIN']))).toBe('/');
  });
});
