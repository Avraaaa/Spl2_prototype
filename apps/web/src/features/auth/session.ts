import type { QueryClient } from '@tanstack/react-query';
import type { PortalUser } from './roles';

export const ME_KEY = ['auth', 'me'] as const;

/** Replace the signed-in identity. The whole cache is dropped first so no stale data survives. */
export function resetSession(qc: QueryClient, user: PortalUser | null): void {
  qc.clear();
  qc.setQueryData(ME_KEY, user);
}
