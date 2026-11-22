import type { Role } from '../auth/roles';

export const canLoadLabelOptions = (roles: Role[]) => roles.includes('DATASOFT_ADMIN');

export type LabelOption = { id: number; name: string };
type LabeledIssue = { confirmed_label: { id: number; name: string } | null };

export function labelOptionSource(roles: Role[], issues: LabeledIssue[]): LabelOption[] | 'admin' {
  if (canLoadLabelOptions(roles)) return 'admin';
  return [...new Map(issues.flatMap(issue => issue.confirmed_label ? [[issue.confirmed_label.id, issue.confirmed_label.name] as const] : [])).entries()]
    .map(([id, name]) => ({ id, name }));
}
