import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { components } from '../../api/generated/schema';
import type { PortalUser } from './roles';

export const ME_KEY = ['auth', 'me'] as const;

/** Extract a readable message from a DRF error body. */
export function errorMessage(error: unknown, fallback = 'Request failed'): string {
  if (!error || typeof error !== 'object') return fallback;
  const body = error as Record<string, unknown>;
  if (typeof body.detail === 'string') return body.detail;
  const parts = Object.entries(body).map(([k, v]) => `${k === 'non_field_errors' ? '' : `${k}: `}${Array.isArray(v) ? v.join(' ') : String(v)}`);
  return parts.length ? parts.join(' · ') : fallback;
}

export function useMe() {
  return useQuery({
    queryKey: ME_KEY,
    queryFn: async (): Promise<PortalUser | null> => {
      const { data, response } = await api.GET('/api/auth/me/');
      if (response.status === 401 || response.status === 403) return null;
      if (!data) throw new Error('API unavailable');
      return data;
    },
    retry: false,
    staleTime: 60_000,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { username: string; password: string }) => {
      await api.GET('/api/auth/csrf/'); // sets the csrftoken cookie
      const { data, error } = await api.POST('/api/auth/login/', { body });
      if (!data) throw new Error(errorMessage(error, 'Login failed'));
      return data;
    },
    onSuccess: user => qc.setQueryData(ME_KEY, user),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { response } = await api.POST('/api/auth/logout/');
      // Only a confirmed server-side logout clears local state; otherwise the session may live on.
      if (!response.ok) throw new Error('Sign-out failed. Your session is still active; please retry.');
    },
    onSuccess: () => {
      qc.clear();
      qc.setQueryData(ME_KEY, null);
    },
    onError: () => qc.invalidateQueries({ queryKey: ME_KEY }),
  });
}

export function useChangePassword() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { current_password: string; new_password: string }) => {
      const { data, error } = await api.POST('/api/auth/change-password/', { body });
      if (!data) throw new Error(errorMessage(error, 'Password change failed'));
      return data;
    },
    onSuccess: user => qc.setQueryData(ME_KEY, user),
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: components['schemas']['PatchedProfileUpdateRequest']) => {
      const { data, error } = await api.PATCH('/api/auth/me/', { body });
      if (!data) throw new Error(errorMessage(error, 'Profile update failed'));
      return data;
    },
    onSuccess: user => qc.setQueryData(ME_KEY, user),
  });
}

export function useChangeUsername() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: components['schemas']['ChangeUsernameRequest']) => {
      const { data, error } = await api.POST('/api/auth/change-username/', { body });
      if (!data) throw new Error(errorMessage(error, 'Username change failed'));
      return data;
    },
    onSuccess: user => qc.setQueryData(ME_KEY, user),
  });
}
