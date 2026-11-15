import { describe, expect, it } from 'vitest';
import { pageTitleFor } from './Shell';

const items = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/issues', label: 'Requests', end: true },
  { to: '/reports', label: 'Reports' },
];

describe('shell page context', () => {
  it('uses useful titles for request routes', () => {
    expect(pageTitleFor('/issues/new', items)).toBe('New request');
    expect(pageTitleFor('/issues/42/edit', items)).toBe('Edit draft');
    expect(pageTitleFor('/issues/42', items)).toBe('Request details');
  });

  it('uses navigation labels for ordinary pages', () => {
    expect(pageTitleFor('/', items)).toBe('Dashboard');
    expect(pageTitleFor('/reports', items)).toBe('Reports');
  });
});
