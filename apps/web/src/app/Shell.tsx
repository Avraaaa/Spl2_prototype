import { Link, NavLink, useNavigate } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useLogout } from '../features/auth/hooks';
import { experienceOf, navFor, type NavItem } from '../features/auth/nav';
import type { PortalUser } from '../features/auth/roles';
import { useIssues } from '../features/issues/hooks';
import { NotificationBell, useUnreadCount } from '../features/notifications/NotificationsPage';

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

export function Shell({ me, children }: { me: PortalUser; children: ReactNode }) {
  const logout = useLogout();
  const navigate = useNavigate();
  const experience = experienceOf(me);
  const console_ = experience === 'console';
  const counts = useBadges(me);
  return (
    <div className={`app ${experience}`}>
      <header className={`topbar ${experience}`}>
        <Link to="/" className="brand">
          <span className="logo">DS</span>
          <span className="brand-text">
            <strong>{console_ ? 'DataSoft Console' : me.organization.name}</strong>
            <span className="muted">{console_ ? 'Internal support workspace' : 'Client portal'}</span>
          </span>
        </Link>
        <nav aria-label={console_ ? 'DataSoft console' : 'Client portal'}>
          {navFor(me).map(item => (
            <NavLink key={item.to} to={item.to} end={item.end}>
              {item.label}
              <NavBadge item={item} counts={counts} />
            </NavLink>
          ))}
          {console_ && <NotificationBell />}
        </nav>
        <div className="who">
          <div>
            <strong>{me.full_name}</strong>
            <small>{me.organization.name}</small>
          </div>
          <Link className="btn small ghost" to="/account/password">
            Password
          </Link>
          <button
            className="btn small"
            onClick={() => logout.mutate(undefined, { onSuccess: () => navigate('/login') })}
          >
            Sign out
          </button>
        </div>
      </header>
      {logout.isError && (
        <p className="alert error" role="alert">
          {logout.error.message}
        </p>
      )}
      <main className="content">{children}</main>
    </div>
  );
}
