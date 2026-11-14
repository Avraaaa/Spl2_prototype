import { QueryClient, QueryObserver } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import { ME_KEY, resetSession } from './session';
import type { PortalUser } from './roles';

const user = (name: string) => ({ full_name: name }) as PortalUser;

describe('resetSession with mounted observers', () => {
  it('notifies an existing ME observer of the new user, then null on logout', () => {
    const qc = new QueryClient();
    qc.setQueryData(ME_KEY, user('Nadia'));
    const observer = new QueryObserver<PortalUser | null>(qc, {
      queryKey: ME_KEY,
      queryFn: () => null,
      staleTime: Infinity,
    });
    const unsubscribe = observer.subscribe(() => undefined);
    expect(observer.getCurrentResult().data?.full_name).toBe('Nadia');

    resetSession(qc, user('Sam'));
    expect(observer.getCurrentResult().data?.full_name).toBe('Sam');

    resetSession(qc, null);
    expect(observer.getCurrentResult().data).toBeNull();
    unsubscribe();
  });

  it('removes other cached queries but keeps the identity query', () => {
    const qc = new QueryClient();
    qc.setQueryData(['issues', 'list', {}], [{ id: 1 }]);
    qc.setQueryData(['report', 'dashboard'], { total: 3 });
    resetSession(qc, user('Sam'));
    expect(qc.getQueryData(['issues', 'list', {}])).toBeUndefined();
    expect(qc.getQueryData(['report', 'dashboard'])).toBeUndefined();
    expect(qc.getQueryData<PortalUser>(ME_KEY)?.full_name).toBe('Sam');
  });
});
