import { useMemo, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { components } from '../../api/generated/schema';
import { errorMessage } from '../auth/hooks';
import { BANK_ROLES, DATASOFT_ROLES, roleLabel, type PortalUser, type Role } from '../auth/roles';

type Organization = components['schemas']['Organization'];
type Credential = components['schemas']['TemporaryCredential'];

const USERS = ['admin', 'users'] as const;
const ORGS = ['admin', 'organizations'] as const;

function useOrganizations() {
  return useQuery({
    queryKey: ORGS,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/admin/organizations/');
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
}

function useUsers(organization: number | null) {
  return useQuery({
    queryKey: [...USERS, organization],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/admin/users/', {
        params: { query: organization ? { organization } : {} },
      });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
}

function CredentialNotice({ credential, onClose }: { credential: Credential; onClose: () => void }) {
  return (
    <div className="alert success" role="status">
      <strong>Temporary password for {credential.user.username}</strong>
      <p>Hand this over securely. It is shown only once, expires in 72 hours and must be changed at first sign-in.</p>
      <code className="secret">{credential.temporary_password}</code>
      <button className="btn ghost" onClick={onClose}>I have recorded it</button>
    </div>
  );
}

function CreateBankForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const create = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST('/api/admin/organizations/', { body: { name, code } });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ORGS }); setName(''); setCode(''); onDone(); },
  });
  return (
    <form className="card form-grid" onSubmit={(e: FormEvent) => { e.preventDefault(); create.mutate(); }}>
      <h3>Register client bank</h3>
      <label>Bank name<input value={name} onChange={e => setName(e.target.value)} required /></label>
      <label>Short code<input value={code} onChange={e => setCode(e.target.value)} required maxLength={20} /></label>
      {create.isError && <p className="alert error">{create.error.message}</p>}
      <button className="btn primary" disabled={create.isPending}>Register bank</button>
    </form>
  );
}

function CreateUserForm({ orgs, onCreated }: { orgs: Organization[]; onCreated: (c: Credential) => void }) {
  const qc = useQueryClient();
  const [orgId, setOrgId] = useState<number | ''>('');
  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [roles, setRoles] = useState<Role[]>([]);
  const org = orgs.find(o => o.id === orgId);
  const available = org ? (org.kind === 'DATASOFT' ? DATASOFT_ROLES : BANK_ROLES) : [];
  const toggle = (role: Role) => {
    if (org?.kind === 'DATASOFT') setRoles([role]); // DataSoft roles are exclusive
    else setRoles(r => (r.includes(role) ? r.filter(x => x !== role) : [...r, role]));
  };
  const create = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST('/api/admin/users/', {
        body: { organization: Number(orgId), username, full_name: fullName, email, roles },
      });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
    onSuccess: credential => {
      qc.invalidateQueries({ queryKey: USERS });
      setUsername(''); setFullName(''); setEmail(''); setRoles([]);
      onCreated(credential);
    },
  });
  return (
    <form className="card form-grid" onSubmit={(e: FormEvent) => { e.preventDefault(); create.mutate(); }}>
      <h3>Create user account</h3>
      <label>Organization
        <select value={orgId} onChange={e => { setOrgId(e.target.value ? Number(e.target.value) : ''); setRoles([]); }} required>
          <option value="">Select…</option>
          {orgs.filter(o => o.is_active).map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
        </select>
      </label>
      <label>Full name<input value={fullName} onChange={e => setFullName(e.target.value)} required /></label>
      <label>Username<input value={username} onChange={e => setUsername(e.target.value)} required minLength={3} /></label>
      <label>Email<input type="email" value={email} onChange={e => setEmail(e.target.value)} required /></label>
      <fieldset>
        <legend>Roles</legend>
        {available.length === 0 && <span className="muted small">Choose an organization first.</span>}
        {available.map(role => (
          <label key={role} className="check">
            <input type={org?.kind === 'DATASOFT' ? 'radio' : 'checkbox'} checked={roles.includes(role)} onChange={() => toggle(role)} />
            {roleLabel(role)}
          </label>
        ))}
      </fieldset>
      {create.isError && <p className="alert error">{create.error.message}</p>}
      <button className="btn primary" disabled={create.isPending || roles.length === 0}>Create account</button>
    </form>
  );
}

function UserRow({ user, me, onCredential }: { user: PortalUser; me: PortalUser; onCredential: (c: Credential) => void }) {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: USERS });
  const deactivate = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST('/api/admin/users/{id}/deactivate/', { params: { path: { id: user.id } } });
      if (!data) throw new Error(errorMessage(error));
    },
    onSuccess: refresh,
  });
  const reset = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST('/api/admin/users/{id}/reset-password/', { params: { path: { id: user.id } } });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
    onSuccess: c => { refresh(); onCredential(c); },
  });
  const failed = deactivate.error ?? reset.error;
  return (
    <tr className={user.is_active ? '' : 'inactive'}>
      <td><strong>{user.full_name}</strong><div className="muted small">{user.username} · {user.email}</div></td>
      <td>{user.organization.name}</td>
      <td>{user.roles.map(r => <span key={r} className="chip">{roleLabel(r)}</span>)}</td>
      <td>
        {!user.is_active ? <span className="chip muted">Deactivated</span>
          : user.must_change_password ? <span className="chip warn">Awaiting first sign-in</span>
          : <span className="chip ok">Active</span>}
      </td>
      <td className="actions">
        {user.is_active && user.id !== me.id && (
          <>
            <button className="btn small" onClick={() => reset.mutate()} disabled={reset.isPending}>Reset password</button>
            <button className="btn small danger" onClick={() => deactivate.mutate()} disabled={deactivate.isPending}>Deactivate</button>
          </>
        )}
        {failed && <div className="alert error small">{failed.message}</div>}
      </td>
    </tr>
  );
}

export function UsersAdminPage({ me }: { me: PortalUser }) {
  const orgs = useOrganizations();
  const [filter, setFilter] = useState<number | null>(null);
  const users = useUsers(filter);
  const [credential, setCredential] = useState<Credential | null>(null);
  const [showBank, setShowBank] = useState(false);
  const banks = useMemo(() => (orgs.data ?? []).filter(o => o.kind === 'BANK').length, [orgs.data]);

  return (
    <section className="stack">
      <div className="page-head">
        <div><h1>Users &amp; banks</h1><p className="muted">{banks} client banks · only DataSoft Administrators can manage accounts.</p></div>
        <button className="btn" onClick={() => setShowBank(s => !s)}>{showBank ? 'Close' : 'Register bank'}</button>
      </div>
      {credential && <CredentialNotice credential={credential} onClose={() => setCredential(null)} />}
      <div className="two-col">
        {orgs.data && <CreateUserForm orgs={orgs.data} onCreated={setCredential} />}
        {showBank && <CreateBankForm onDone={() => setShowBank(false)} />}
      </div>
      <div className="card">
        <div className="toolbar">
          <h3>Accounts</h3>
          <select value={filter ?? ''} onChange={e => setFilter(e.target.value ? Number(e.target.value) : null)} aria-label="Filter by organization">
            <option value="">All organizations</option>
            {(orgs.data ?? []).map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
        </div>
        {users.isError && <p className="alert error">{users.error.message}</p>}
        <div className="table-wrap">
          <table>
            <thead><tr><th>User</th><th>Organization</th><th>Roles</th><th>Status</th><th /></tr></thead>
            <tbody>{(users.data ?? []).map(u => <UserRow key={u.id} user={u} me={me} onCredential={setCredential} />)}</tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
