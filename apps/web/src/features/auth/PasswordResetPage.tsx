import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import { errorMessage } from './hooks';

export function readResetParams(href: string) {
  const current = new URL(href);
  const fragment = new URLSearchParams(current.hash.replace(/^#/, ''));
  return {
    uid: current.searchParams.get('uid') ?? '',
    token: fragment.get('token') ?? current.searchParams.get('token') ?? '',
  };
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setPending(true);
    setError('');
    try {
      const { response, error: apiError } = await api.POST('/api/auth/forgot-password/', { body: { email } });
      if (response.status === 202) setSent(true);
      else setError(errorMessage(apiError));
    } catch {
      setError('Could not send the request. Please try again.');
    } finally {
      setPending(false);
    }
  };
  return (
    <main className="auth-shell"><form className="card auth-card" onSubmit={submit}>
      <h1>Reset your password</h1>
      {sent ? <p role="status">If an account matches that email, a one-time reset link has been sent.</p> : <>
        <p className="muted">Enter the email address registered to your account.</p>
        <label>Email<input type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} required /></label>
        {error && <p role="alert" className="alert error">{error}</p>}
        <button className="btn primary" disabled={pending}>{pending ? 'Sending…' : 'Send reset link'}</button>
      </>}
      <Link to="/login">Back to sign in</Link>
    </form></main>
  );
}

export function CompletePasswordResetPage() {
  const [initial] = useState(() => readResetParams(window.location.href));
  const { uid, token } = initial;
  const [password, setPassword] = useState('');
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  useEffect(() => {
    const current = new URL(window.location.href);
    const queryToken = current.searchParams.get('token');
    const fragment = new URLSearchParams(current.hash.replace(/^#/, ''));
    const fragmentToken = fragment.get('token');

    // Migrate old links into the fragment, then remove the secret from browser history.
    current.searchParams.delete('token');
    if (queryToken && !fragmentToken) {
      current.hash = new URLSearchParams({ token: queryToken }).toString();
      window.history.replaceState(null, '', current.pathname + current.search + current.hash);
    }
    if (queryToken || fragmentToken) {
      window.history.replaceState(null, '', current.pathname + current.search);
    }
  }, []);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setPending(true);
    setError('');
    try {
      const { response, error: apiError } = await api.POST('/api/auth/reset-password/', { body: { uid, token, password } });
      if (response.status === 204) setDone(true);
      else setError(errorMessage(apiError));
    } catch {
      setError('Could not reset the password. Please try again.');
    } finally {
      setPending(false);
    }
  };
  return (
    <main className="auth-shell"><form className="card auth-card" onSubmit={submit}>
      <h1>Choose a new password</h1>
      {done ? <p role="status">Your password was reset. You can sign in now.</p> : <>
        <label>New password<input type="password" autoComplete="new-password" minLength={8} value={password} onChange={e => setPassword(e.target.value)} required /></label>
        {error && <p role="alert" className="alert error">{error}</p>}
        <button className="btn primary" disabled={pending || !uid || !token}>{pending ? 'Saving…' : 'Set new password'}</button>
      </>}
      <Link to="/login">Back to sign in</Link>
    </form></main>
  );
}
