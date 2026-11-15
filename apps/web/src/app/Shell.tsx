import { useState, type ReactNode } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useLogout } from '../features/auth/hooks';
import { experienceOf, navFor, type NavItem } from '../features/auth/nav';
import type { PortalUser } from '../features/auth/roles';
import { useIssues } from '../features/issues/hooks';
import { NotificationBell, useUnreadCount } from '../features/notifications/NotificationsPage';
import { LockIcon, LogoutIcon, MenuIcon, NavIcon } from '../features/ui/icons';

function useBadges(me: PortalUser) {
  const verifier = me.roles.includes('ISSUE_VERIFIER');
  const awaiting = useIssues({ status: 'AWAITING_VERIFICATION' }, verifier && experienceOf(me) === 'client');
  const unread = useUnreadCount();
  return { awaiting: awaiting.data?.length ?? 0, unread: unread.data ?? 0 } as const;
}

function NavBadge({ item, counts }: { item: NavItem; counts: { awaiting: number; unread: number } }) {
  const value = item.badge ? counts[item.badge] : 0;
  return value > 0 ? <span className="nav-badge">{value}</span> : null;
}

export function pageTitleFor(pathname: string, items: NavItem[]): string {
  if (pathname === '/issues/new') return 'New request';
  if (/^\/issues\/\d+\/edit$/.test(pathname)) return 'Edit draft';
  if (/^\/issues\/\d+$/.test(pathname)) return 'Request details';
  if (pathname === '/account/password') return 'Account settings';
  const current = [...items]
    .sort((left, right) => right.to.length - left.to.length)
    .find(item => pathname === item.to || (item.to !== '/' && pathname.startsWith(`${item.to}/`)));
  return current?.label ?? 'Service portal';
}

export function Shell({ me, children }: { me: PortalUser; children: ReactNode }) {
  const logout = useLogout();
  const navigate = useNavigate();
  const location = useLocation();
  const [navOpen, setNavOpen] = useState(false);
  const experience = experienceOf(me);
  const console_ = experience === 'console';
  const counts = useBadges(me);
  const items = navFor(me);
  const pageTitle = pageTitleFor(location.pathname, items);
  const initials = (console_ ? 'DS' : me.organization.code || me.organization.name.slice(0, 2)).slice(0, 3);

  return (
    <div className={`app app-shell ${experience}`}>
      <aside className={`sidebar ${experience}${navOpen ? ' is-open' : ''}`}>
        <Link to="/" className="sidebar-brand" onClick={() => setNavOpen(false)}>
          <span className="logo">{initials}</span>
          <span className="brand-text">
            <strong>{console_ ? 'DataSoft' : me.organization.name}</strong>
            <span>{console_ ? 'Support Console' : 'Client Portal'}</span>
          </span>
        </Link>
        <nav aria-label={console_ ? 'DataSoft console' : 'Client portal'}>
          <span className="nav-section-label">Workspace</span>
          {items.map(item => (
            <NavLink key={item.to} to={item.to} end={item.end} onClick={() => setNavOpen(false)}>
              <NavIcon label={item.label} />
              <span>{item.label}</span>
              <NavBadge item={item} counts={counts} />
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className="presence-dot" />
          <span>Secure workspace</span>
        </div>
      </aside>

      <div className="app-workspace">
        <header className="workspace-topbar">
          <button
            type="button"
            className="icon-button nav-toggle"
            aria-label="Toggle navigation"
            aria-expanded={navOpen}
            onClick={() => setNavOpen(open => !open)}
          >
            <MenuIcon />
          </button>
          <div className="page-context">
            <span>{console_ ? 'DataSoft Console' : me.organization.name}</span>
            <strong>{pageTitle}</strong>
          </div>
          <div className="topbar-actions">
            <NotificationBell />
            <div className="user-summary">
              <span className="avatar" aria-hidden="true">
                {me.full_name
                  .split(' ')
                  .map(part => part[0])
                  .join('')
                  .slice(0, 2)}
              </span>
              <span>
                <strong>{me.full_name}</strong>
                <small>{me.organization.name}</small>
              </span>
            </div>
            <Link className="icon-button" to="/account/password" aria-label="Account and password">
              <LockIcon />
            </Link>
            <button
              className="icon-button"
              aria-label="Sign out"
              disabled={logout.isPending}
              onClick={() => logout.mutate(undefined, { onSuccess: () => navigate('/login') })}
            >
              <LogoutIcon />
            </button>
          </div>
        </header>
        {logout.isError && (
          <p className="alert error shell-alert" role="alert">
            {logout.error.message}
          </p>
        )}
        <main className="content">{children}</main>
      </div>
      {navOpen && <button className="nav-scrim" aria-label="Close navigation" onClick={() => setNavOpen(false)} />}
    </div>
  );
}
