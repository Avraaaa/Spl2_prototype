import type { components } from '../../api/generated/schema';

export type Role = components['schemas']['RolesEnum'];
export type PortalUser = components['schemas']['PortalUser'];

const LABELS: Record<Role, string> = {
  ISSUE_OFFICER: 'Issue Officer',
  ISSUE_VERIFIER: 'Issue Verifier',
  DATASOFT_ADMIN: 'DataSoft Administrator',
  SUPPORT_AGENT: 'Support Agent',
};

export const BANK_ROLES: Role[] = ['ISSUE_OFFICER', 'ISSUE_VERIFIER'];
export const DATASOFT_ROLES: Role[] = ['DATASOFT_ADMIN', 'SUPPORT_AGENT'];

export const roleLabel = (role: Role) => LABELS[role];

/** UI convenience only — every action is authorized again by Django. */
export const hasRole = (user: Pick<PortalUser, 'roles'>, role: Role) => user.roles.includes(role);

export function landingFor(user: Pick<PortalUser, 'roles' | 'must_change_password'> | null): string {
  if (!user) return '/login';
  if (user.must_change_password) return '/change-password';
  return '/';
}
