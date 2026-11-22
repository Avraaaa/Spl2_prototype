import { describe, expect, it } from 'vitest';
import { canLoadLabelOptions, labelOptionSource } from './labelFilter';

describe('issue label filter access', () => {
  it('loads the admin-only label directory only for DataSoft administrators', () => {
    expect(canLoadLabelOptions(['DATASOFT_ADMIN'])).toBe(true);
    expect(canLoadLabelOptions(['SUPPORT_AGENT'])).toBe(false);
    expect(canLoadLabelOptions(['ISSUE_OFFICER'])).toBe(false);
  });

  it('uses the admin directory for admins and current confirmed labels for support agents', () => {
    const issues = [
      { confirmed_label: { id: 3, name: 'Payments' } },
      { confirmed_label: { id: 3, name: 'Payments' } },
      { confirmed_label: { id: 7, name: 'Access' } },
      { confirmed_label: null },
    ];
    expect(labelOptionSource(['DATASOFT_ADMIN'], issues)).toBe('admin');
    expect(labelOptionSource(['SUPPORT_AGENT'], issues)).toEqual([
      { id: 3, name: 'Payments' }, { id: 7, name: 'Access' },
    ]);
  });
});
