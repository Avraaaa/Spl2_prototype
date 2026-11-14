import { QueryClient } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import { ME_KEY, resetSession } from './session';
import type { PortalUser } from './roles';

const user = (name: string) => ({ full_name: name }) as PortalUser;

describe('resetSession', () => {
  it('drops cached data from the previous user on login', () => {
    const qc = new QueryClient();
    qc.setQueryData(ME_KEY, user('Nadia'));
    qc.setQueryData(['issues', 'list', {}], [{ id: 1 }]);
    resetSession(qc, user('Sam'));
    expect(qc.getQueryData<PortalUser>(ME_KEY)?.full_name).toBe('Sam');
    expect(qc.getQueryData(['issues', 'list', {}])).toBeUndefined();
  });

  it('clears everything on logout', () => {
    const qc = new QueryClient();
    qc.setQueryData(['report', 'dashboard'], { total: 3 });
    resetSession(qc, null);
    expect(qc.getQueryData(ME_KEY)).toBeNull();
    expect(qc.getQueryData(['report', 'dashboard'])).toBeUndefined();
  });
});
