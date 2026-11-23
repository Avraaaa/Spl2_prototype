import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
import { errorMessage } from '../auth/hooks';
import { PageHeader } from '../ui/PageHeader';

export function AuditLogPage() {
  const [organization, setOrganization] = useState('');
  const [action, setAction] = useState('');
  const [actor, setActor] = useState('');
  const [after, setAfter] = useState('');
  const [before, setBefore] = useState('');
  const params = { ...(organization ? { organization } : {}), ...(action ? { action } : {}), ...(actor ? { actor } : {}), ...(after ? { after } : {}), ...(before ? { before } : {}) };
  const audit = useQuery({
    queryKey: ['admin', 'audit-records', params],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/audit/records/', { params: { query: params } });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
  const queryString = new URLSearchParams(params).toString();
  const exportHref = `/api/audit/records/export/${queryString ? `?${queryString}` : ''}`;
  const integrity = audit.data?.integrity;
  const banks = audit.data?.organizations ?? [];

  return <section className="stack">
    <PageHeader title="Audit log" subtitle="Append-only activity records and hash-chain integrity for each bank." actions={<a className="btn primary" href={exportHref}>Export CSV</a>} />
    <div className="card form-grid">
      <label>Bank<select value={organization} onChange={event => setOrganization(event.target.value)}><option value="">All banks</option>{banks.map(bank => <option key={bank.code} value={bank.code}>{bank.name} ({bank.code})</option>)}</select></label>
      <label>Action<input value={action} onChange={event => setAction(event.target.value)} placeholder="e.g. issue.submitted" /></label>
      <label>Actor<input value={actor} onChange={event => setActor(event.target.value)} /></label>
      <label>From<input type="date" value={after} onChange={event => setAfter(event.target.value)} /></label>
      <label>Through<input type="date" value={before} onChange={event => setBefore(event.target.value)} /></label>
    </div>
    {audit.isError && <p role="alert" className="alert error">{audit.error.message}</p>}
    <div className="card stack">
      <h2>Chain integrity</h2>
      {organization ? <Integrity valid={integrity?.valid} firstInvalidSequence={integrity?.first_invalid_sequence} /> : banks.map(bank => <p key={bank.code}><strong>{bank.name} ({bank.code}):</strong> <Integrity valid={bank.valid} firstInvalidSequence={bank.first_invalid_sequence} /></p>)}
    </div>
    <div className="card stack">
      <h2>Records{audit.data ? ` (${audit.data.results.length}${audit.data.results.length === 500 ? '+' : ''})` : ''}</h2>
      {audit.isPending ? <p className="muted">Loading audit records…</p> : <div className="table-wrap"><table><thead><tr><th>Time</th><th>Bank</th><th>Sequence</th><th>Actor</th><th>Action</th><th>Details</th><th>Record hash</th></tr></thead><tbody>{audit.data?.results.map(row => <tr key={row.id}><td>{new Date(row.created_at).toLocaleString()}</td><td>{row.organization_name} ({row.organization_code})</td><td>{row.sequence}</td><td>{row.actor_username}</td><td>{row.action}</td><td><code>{JSON.stringify(row.payload)}</code></td><td><code>{row.record_hash}</code></td></tr>)}</tbody></table>{audit.data?.results.length === 0 && <p className="muted">No matching audit records.</p>}</div>}
    </div>
  </section>;
}

function Integrity({ valid, firstInvalidSequence }: { valid?: boolean; firstInvalidSequence?: number | null }) {
  if (valid === undefined) return <span className="muted">Not available</span>;
  if (valid) return <span className="badge">Valid</span>;
  return <span className="alert error">Broken at sequence {firstInvalidSequence ?? 'unknown'}</span>;
}
