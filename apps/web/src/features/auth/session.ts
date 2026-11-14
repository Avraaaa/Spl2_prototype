import type { QueryClient } from '@tanstack/react-query';
import type { PortalUser } from './roles';

export const ME_KEY = ['auth', 'me'] as const;

/**
 * Replace the signed-in identity and drop all other cached user data.
 * Not qc.clear(): that detaches queries from mounted observers, which would then never see the new identity.
 */
export function resetSession(qc: QueryClient, user: PortalUser | null): void {
  qc.setQueryData(ME_KEY, user);
  qc.removeQueries({ predicate: q => q.queryKey[0] !== ME_KEY[0] });
}
