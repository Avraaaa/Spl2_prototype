import { Link, Navigate, NavLink, Route, Routes, useNavigate } from 'react-router-dom';
import { ChangePasswordPage } from '../features/auth/ChangePasswordPage';
import { LoginPage } from '../features/auth/LoginPage';
import { useLogout, useMe } from '../features/auth/hooks';
import { hasRole, landingFor, roleLabel, type PortalUser } from '../features/auth/roles';
import { UsersAdminPage } from '../features/tenants/UsersAdminPage';

function Shell({ me, children }: { me: PortalUser; children: React.ReactNode }) {
  const logout = useLogout();
  const navigate = useNavigate();
  const isAdmin = hasRole(me, 'DATASOFT_ADMIN');
  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand"><span className="logo">DS</span><strong>DataSoft</strong><span className="muted">Service Requests</span></Link>
        <nav>
          <NavLink to="/" end>Dashboard</NavLink>
          {isAdmin && <NavLink to="/admin/users">Users &amp; banks</NavLink>}
        </nav>
        <div className="who">
          <div><strong>{me.full_name}</strong><small>{me.organization.name}</small></div>
          <Link className="btn small ghost" to="/account/password">Password</Link>
          <button className="btn small" onClick={() => logout.mutate(undefined, { onSuccess: () => navigate('/login') })}>Sign out</button>
        </div>
      </header>
      {logout.isError && <p className="alert error" role="alert">{logout.error.message}</p>}
      <main className="content">{children}</main>
    </div>
  );
}

function Dashboard({ me }: { me: PortalUser }) {
  const bank = me.organization.kind === 'BANK';
  return (
    <section className="stack">
      <div className="page-head">
        <div>
          <p className="eyebrow">{bank ? 'CLIENT BANK' : 'DATASOFT'}</p>
          <h1>Welcome, {me.full_name.split(' ')[0]}</h1>
          <p className="muted">{me.organization.name} · {me.roles.map(roleLabel).join(' + ')}</p>
        </div>
      </div>
      <div className="grid">
        {hasRole(me, 'ISSUE_OFFICER') && <div className="card"><h3>Issue Officer</h3><p className="muted">Draft, authorize and submit your bank's service requests.</p></div>}
        {hasRole(me, 'ISSUE_VERIFIER') && <div className="card"><h3>Issue Verifier</h3><p className="muted">Verify delivered fixes for your bank or report a failed verification.</p></div>}
        {hasRole(me, 'SUPPORT_AGENT') && <div className="card"><h3>Support Agent</h3><p className="muted">Review submitted requests, plan delivery dates and deliver fixes.</p></div>}
        {hasRole(me, 'DATASOFT_ADMIN') && <div className="card"><h3>Administration</h3><p className="muted">Register client banks and manage user accounts and roles.</p><Link className="btn primary" to="/admin/users">Manage users</Link></div>}
      </div>
      <p className="muted small">Issue registration and the request lifecycle arrive in the next tasks (P2-T1, P2-T2).</p>
    </section>
  );
}

export function App() {
  const me = useMe();
  if (me.isPending) return <div className="center muted">Loading…</div>;
  if (me.isError) return <div className="center"><p className="alert error">The API is unreachable. Is Django running on :8000?</p></div>;
  const user = me.data;
  const authed = (el: (u: PortalUser) => React.ReactNode, needs?: 'DATASOFT_ADMIN') => {
    if (!user) return <Navigate to="/login" replace />;
    if (user.must_change_password) return <Navigate to="/change-password" replace />;
    if (needs && !hasRole(user, needs)) return <Navigate to="/" replace />;
    return <Shell me={user}>{el(user)}</Shell>;
  };
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/change-password" element={<ChangePasswordPage />} />
      <Route path="/account/password" element={user ? <ChangePasswordPage /> : <Navigate to="/login" replace />} />
      <Route path="/" element={authed(u => <Dashboard me={u} />)} />
      <Route path="/admin/users" element={authed(u => <UsersAdminPage me={u} />, 'DATASOFT_ADMIN')} />
      <Route path="*" element={<Navigate to={landingFor(user ?? null)} replace />} />
    </Routes>
  );
}
