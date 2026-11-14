import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
import { errorMessage } from '../auth/hooks';

export const ISSUE_KEY = ['issues'] as const;

export type IssueFilters = {
  status?: string;
  request_type?: string;
  priority?: string;
  search?: string;
  organization?: string;
  assignee?: 'me';
  overdue?: boolean;
  ordering?: 'oldest';
};

/** Drops empty filter values so they are not sent as empty query parameters. */
export function cleanFilters(filters: IssueFilters) {
  const query: Record<string, string | number | boolean> = {};
  for (const [key, value] of Object.entries(filters)) {
    if (value === '' || value === undefined || value === false) continue;
    query[key] = key === 'organization' ? Number(value) : value;
  }
  return query as {
    status?: string;
    request_type?: string;
    priority?: string;
    search?: string;
    organization?: number;
    assignee?: string;
    overdue?: boolean;
    ordering?: string;
  };
}

export function useIssues(filters: IssueFilters = {}, enabled = true) {
  return useQuery({
    queryKey: [...ISSUE_KEY, 'list', filters],
    enabled,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/issues/', { params: { query: cleanFilters(filters) } });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
}

export function useIssue(id: number) {
  return useQuery({
    queryKey: [...ISSUE_KEY, id],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/issues/{id}/', { params: { path: { id } } });
      if (!data) throw new Error(errorMessage(error, 'Request unavailable'));
      return data;
    },
    enabled: Number.isInteger(id) && id > 0,
  });
}

export function useProducts() {
  return useQuery({
    queryKey: ['products'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/products/');
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
}

export function useBanks(enabled: boolean) {
  return useQuery({
    queryKey: ['report', 'banks'],
    enabled,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/reports/banks/');
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
}
