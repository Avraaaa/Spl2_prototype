import { describe, expect, it } from 'vitest';
import { experienceOf, navFor, redirectFor } from './nav';
import type { Role } from './roles';

const u = (...roles: Role[]) => ({ roles });
const labels = (...roles: Role[]) => navFor(u(...roles)).map(i => i.label);

describe('navigation by role', () => {
  it('officer sees the client portal with New request', () => {
    expect(experienceOf(u('ISSUE_OFFICER'))).toBe('client');
    expect(labels('ISSUE_OFFICER')).toEqual(['Dashboard', 'Requests', 'New request', 'Reports', 'Notifications']);
  });

  it('verifier sees Awaiting my verification, not New request', () => {
    const items = labels('ISSUE_VERIFIER');
    expect(items).toContain('Awaiting my verification');
    expect(items).not.toContain('New request');
  });

  it('client nav never shows console areas', () => {
    const items = labels('ISSUE_OFFICER', 'ISSUE_VERIFIER');
    for (const hidden of ['Tasks board', 'Admin', 'Intake queue', 'My work']) expect(items).not.toContain(hidden);
  });

  it('support agent sees the console without Admin', () => {
    expect(experienceOf(u('SUPPORT_AGENT'))).toBe('console');
    const items = labels('SUPPORT_AGENT');
    expect(items).toEqual(['Dashboard', 'Intake queue', 'All requests', 'My work', 'Tasks board', 'Reports']);
  });

  it('administrator also sees Admin', () => {
    expect(labels('DATASOFT_ADMIN')).toContain('Admin');
  });
});

describe('route guards', () => {
  it('redirects bank users away from console routes', () => {
    for (const path of ['/queue', '/my-work', '/tasks', '/admin', '/admin/users']) {
      expect(redirectFor(u('ISSUE_OFFICER'), path)).toBe('/');
    }
  });

  it('redirects staff away from client-only routes', () => {
    for (const path of ['/issues/new', '/awaiting', '/issues/4/edit']) {
      expect(redirectFor(u('SUPPORT_AGENT'), path)).toBe('/');
    }
  });

  it('keeps Admin for administrators only', () => {
    expect(redirectFor(u('SUPPORT_AGENT'), '/admin/users')).toBe('/');
    expect(redirectFor(u('DATASOFT_ADMIN'), '/admin/users')).toBeNull();
  });

  it('allows shared routes', () => {
    expect(redirectFor(u('ISSUE_OFFICER'), '/issues/12')).toBeNull();
    expect(redirectFor(u('SUPPORT_AGENT'), '/reports')).toBeNull();
    expect(redirectFor(u('ISSUE_OFFICER'), '/issues/new')).toBeNull();
  });
});
