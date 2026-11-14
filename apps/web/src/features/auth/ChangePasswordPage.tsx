import { useState, type FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useChangePassword, useLogout, useMe } from './hooks';

export function ChangePasswordPage() {
  const me = useMe();
  const change = useChangePassword();
  const logout = useLogout();
  const navigate = useNavigate();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');

  if (me.isPending) return null;
  if (!me.data) return <Navigate to="/login" replace />;
  const forced = me.data.must_change_password;
  const mismatch = confirm.length > 0 && next !== confirm;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (mismatch) return;
    change.mutate({ current_password: current, new_password: next }, { onSuccess: () => navigate('/', { replace: true }) });
  };

  return (
    <main className="auth-shell">
      <form className="card auth-card" onSubmit={submit}>
        <h1>{forced ? 'Set your password' : 'Change password'}</h1>
        {forced && <p className="alert info">You signed in with a temporary password. Choose a new password to continue.</p>}
        <label>{forced ? 'Temporary password' : 'Current password'}<input type="password" autoComplete="current-password" value={current} onChange={e => setCurrent(e.target.value)} required /></label>
        <label>New password<input type="password" autoComplete="new-password" value={next} onChange={e => setNext(e.target.value)} required minLength={8} /></label>
        <label>Confirm new password<input type="password" autoComplete="new-password" value={confirm} onChange={e => setConfirm(e.target.value)} required /></label>
        {mismatch && <p className="alert error">Passwords do not match.</p>}
        {change.isError && <p className="alert error" role="alert">{change.error.message}</p>}
        {logout.isError && <p className="alert error" role="alert">{logout.error.message}</p>}
        <button className="btn primary" disabled={change.isPending || mismatch}>Save password</button>
        {forced
          ? <button type="button" className="btn ghost" onClick={() => logout.mutate(undefined, { onSuccess: () => navigate('/login') })}>Sign out</button>
          : <button type="button" className="btn ghost" onClick={() => navigate(-1)}>Cancel</button>}
      </form>
    </main>
  );
}
