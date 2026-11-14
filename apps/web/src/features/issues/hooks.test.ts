import { describe, expect, it } from 'vitest';
import { cleanFilters } from './hooks';

describe('cleanFilters', () => {
  it('drops empty values and converts the bank id', () => {
    expect(cleanFilters({ status: '', search: 'x', organization: '4', overdue: false })).toEqual({
      search: 'x',
      organization: 4,
    });
  });

  it('keeps queue filters', () => {
    expect(cleanFilters({ status: 'SUBMITTED', ordering: 'oldest', assignee: 'me', overdue: true })).toEqual({
      status: 'SUBMITTED',
      ordering: 'oldest',
      assignee: 'me',
      overdue: true,
    });
  });
});
