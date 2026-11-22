import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useLogin, useMe } from './hooks';
import { landingFor } from './roles';

export function LoginPage() {
  const me = useMe();
  const login = useLogin();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  if (me.data) return <Navigate to={landingFor(me.data)} replace />;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    login.mutate({ username, password }, { onSuccess: user => navigate(landingFor(user), { replace: true }) });
  };

  return (
    <main className="auth-shell">
      <section className="auth-brand-panel" aria-label="DataSoft service portal">
        <div className="auth-brand-mark">
          <span className="logo">DS</span>
          <strong>DataSoft</strong>
        </div>
        <div>
          <p className="eyebrow">CLIENT SERVICE OPERATIONS</p>
          <h1>One secure workspace for every service request.</h1>
          <p>Track intake, delivery, verification and reporting with clear ownership and a complete history.</p>
        </div>
        <div className="auth-trust">
          <span /> Tenant-isolated · Auditable · Built for support teams
        </div>
      </section>
      <section className="auth-form-panel">
        <form className="auth-card" onSubmit={submit}>
          <div>
            <p className="eyebrow">WELCOME BACK</p>
            <h1>Sign in to your portal</h1>
            <p className="muted">Use the account provided by your DataSoft administrator.</p>
          </div>
          <label>
            Username
            <input autoComplete="username" value={username} onChange={event => setUsername(event.target.value)} required autoFocus />
          </label>
          <label>
            Password
            <input type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} required />
          </label>
          {login.isError && (
            <p className="alert error" role="alert">
              {login.error.message}
            </p>
          )}
          <button className="btn primary auth-submit" disabled={login.isPending}>
            {login.isPending ? 'Signing in…' : 'Sign in'}
          </button>
          <Link to="/forgot-password">Forgot your password?</Link>
          <p className="muted small">No public registration. Accounts are managed by DataSoft.</p>
        </form>
      </section>
    </main>
  );
}
