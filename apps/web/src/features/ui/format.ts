export const formatDate = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleDateString() : '—';

export const formatDateTime = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleString() : '—';
