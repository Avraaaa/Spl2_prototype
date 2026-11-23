import { hasRole, type PortalUser } from './roles';

type RoleHolder = Pick<PortalUser, 'roles'>;
export type Experience = 'client' | 'console';
export type NavItem = { to: string; label: string; end?: boolean; badge?: 'awaiting' | 'unread' };

export const isStaff = (user: RoleHolder) => hasRole(user, 'SUPPORT_AGENT') || hasRole(user, 'DATASOFT_ADMIN');

export const experienceOf = (user: RoleHolder): Experience => (isStaff(user) ? 'console' : 'client');

/** Client portal for bank users; DataSoft console for staff. UX only — Django enforces access. */
export function navFor(user: RoleHolder): NavItem[] {
  if (experienceOf(user) === 'console') {
    const items: NavItem[] = [
      { to: '/', label: 'Dashboard', end: true },
      { to: '/queue', label: 'Intake queue' },
      { to: '/issues', label: 'All requests', end: true },
      { to: '/my-work', label: 'My work' },
      // ANCHOR P8-T4 console nav (request board)
      { to: '/tasks', label: 'Tasks board' },
      { to: '/reports', label: 'Reports' },
      // ANCHOR P8-T5 console nav (analytics)
    ];
    if (hasRole(user, 'DATASOFT_ADMIN')) items.push({ to: '/admin', label: 'Admin' });
    return items;
  }
  const items: NavItem[] = [
    { to: '/', label: 'Dashboard', end: true },
    { to: '/issues', label: 'Requests', end: true },
  ];
  if (hasRole(user, 'ISSUE_OFFICER')) items.push({ to: '/issues/new', label: 'New request' });
  if (hasRole(user, 'ISSUE_VERIFIER')) items.push({ to: '/awaiting', label: 'Awaiting my verification', badge: 'awaiting' });
  items.push({ to: '/reports', label: 'Reports' });
  // ANCHOR P8-T5 client nav (analytics)
  items.push({ to: '/notifications', label: 'Notifications', badge: 'unread' });
  return items;
}

const CONSOLE_ONLY = ['/queue', '/my-work', '/tasks', '/admin'];
const CLIENT_ONLY = ['/issues/new', '/awaiting'];

const under = (path: string, prefix: string) => path === prefix || path.startsWith(`${prefix}/`);

/** Where a user must be redirected when opening a route of the other experience; null = allowed. */
export function redirectFor(user: RoleHolder, path: string): string | null {
  const console_ = experienceOf(user) === 'console';
  if (console_ && (CLIENT_ONLY.some(p => under(path, p)) || /^\/issues\/\d+\/edit$/.test(path))) return '/';
  if (!console_ && CONSOLE_ONLY.some(p => under(path, p))) return '/';
  if (path.startsWith('/admin') && !hasRole(user, 'DATASOFT_ADMIN')) return '/';
  return null;
}
