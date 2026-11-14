import { useState, type FormEvent } from 'react';
import { useChangeUsername, useUpdateProfile } from './hooks';
import type { PortalUser } from './roles';

export function ProfileSettings({ user }: { user: PortalUser }) {
  const profile = useUpdateProfile();
  const usernameChange = useChangeUsername();
  const [fullName, setFullName] = useState(user.full_name);
  const [email, setEmail] = useState(user.email);
  const [username, setUsername] = useState(user.username);
  const [password, setPassword] = useState('');

  const saveProfile = (event: FormEvent) => {
    event.preventDefault();
    profile.mutate({ full_name: fullName, email });
  };
  const saveUsername = (event: FormEvent) => {
    event.preventDefault();
    usernameChange.mutate(
      { username, current_password: password },
      { onSuccess: () => setPassword('') },
    );
  };

  return (
    <section className="stack" aria-label="Profile settings">
      <form className="card auth-card" onSubmit={saveProfile}>
        <h2>Profile</h2>
        <label>Full name<input value={fullName} onChange={event => setFullName(event.target.value)} maxLength={200} required /></label>
        <label>Email<input type="email" value={email} onChange={event => setEmail(event.target.value)} required /></label>
        {profile.isError && <p className="alert error" role="alert">{profile.error.message}</p>}
        {profile.isSuccess && <p className="alert info" role="status">Profile saved.</p>}
        <button className="btn primary" disabled={profile.isPending}>Save profile</button>
      </form>
      <form className="card auth-card" onSubmit={saveUsername}>
        <h2>Change username</h2>
        <label>Username<input autoComplete="username" value={username} onChange={event => setUsername(event.target.value)} minLength={3} maxLength={150} required /></label>
        <label>Current password<input type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} required /></label>
        {usernameChange.isError && <p className="alert error" role="alert">{usernameChange.error.message}</p>}
        {usernameChange.isSuccess && <p className="alert info" role="status">Username saved.</p>}
        <button className="btn primary" disabled={usernameChange.isPending}>Save username</button>
      </form>
    </section>
  );
}
