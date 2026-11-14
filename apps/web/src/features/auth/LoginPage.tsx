import { useState, type FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useLogin, useMe } from './hooks';
import { landingFor } from './roles';

export function LoginPage() {
  const me = useMe();
  const login = useLogin();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  if (me.data) return <Navigate to={landingFor(me.data)} replace />;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    login.mutate({ username, password }, { onSuccess: user => navigate(landingFor(user), { replace: true }) });
  };

  return (
    <main className="auth-shell">
      <form className="card auth-card" onSubmit={submit}>
        <div className="brand"><span className="logo">DS</span><div><strong>DataSoft</strong><small>Service Request Portal</small></div></div>
        <h1>Sign in</h1>
        <label>Username<input autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required autoFocus /></label>
        <label>Password<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required /></label>
        {login.isError && <p className="alert error" role="alert">{login.error.message}</p>}
        <button className="btn primary" disabled={login.isPending}>{login.isPending ? 'Signing in…' : 'Sign in'}</button>
        <p className="muted small">Accounts are created by the DataSoft Administrator. There is no self-registration.</p>
      </form>
    </main>
  );
}
