import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { components } from '../../api/generated/schema';
import { errorMessage } from '../auth/hooks';
import { hasRole, type PortalUser } from '../auth/roles';
import { WorkflowActions, WorkflowSettingsPanel } from '../workflow/WorkflowActions';
import { IssueCollaboration } from './IssueCollaboration';

type Issue = components['schemas']['Issue'];
type Product = components['schemas']['Product'];
type Draft = components['schemas']['IssueWriteRequest'];

const ISSUE_KEY = ['issues'] as const;
const PRODUCT_KEY = ['products'] as const;

function useProducts() {
  return useQuery({
    queryKey: PRODUCT_KEY,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/products/');
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
}

function useIssues(filters: { status: string; request_type: string; priority: string; search: string }) {
  return useQuery({
    queryKey: [...ISSUE_KEY, filters],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/issues/', {
        params: { query: {
          ...(filters.status ? { status: filters.status } : {}),
          ...(filters.request_type ? { request_type: filters.request_type } : {}),
          ...(filters.priority ? { priority: filters.priority } : {}),
          ...(filters.search ? { search: filters.search } : {}),
        } },
      });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
}

function useIssue(id: number) {
  return useQuery({
    queryKey: [...ISSUE_KEY, id],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/issues/{id}/', { params: { path: { id } } });
      if (!data) throw new Error(errorMessage(error, 'Request unavailable'));
      return data;
    },
    enabled: Number.isInteger(id) && id > 0,
  });
}

export function IssuesListPage({ me }: { me: PortalUser }) {
  const [filters, setFilters] = useState({ status: '', request_type: '', priority: '', search: '' });
  const issues = useIssues(filters);
  const officer = hasRole(me, 'ISSUE_OFFICER');
  const update = (name: keyof typeof filters, value: string) => setFilters(f => ({ ...f, [name]: value }));
  return <section className="stack">
    <div className="page-head"><div><h1>Service requests</h1><p className="muted">Requests visible to your organization.</p></div>
      {officer && <Link className="btn primary" to="/issues/new">New draft</Link>}</div>
    {hasRole(me, 'DATASOFT_ADMIN') && <WorkflowSettingsPanel />}
    <div className="card toolbar">
      <input aria-label="Search title or reference" placeholder="Search title or reference" value={filters.search} onChange={e => update('search', e.target.value)} />
      <select aria-label="Status" value={filters.status} onChange={e => update('status', e.target.value)}><option value="">All statuses</option>{['DRAFT', 'SUBMITTED', 'ACCEPTED', 'REJECTED', 'PENDING', 'IN_PROGRESS', 'AWAITING_VERIFICATION', 'VERIFIED', 'CLOSED'].map(status => <option key={status} value={status}>{status.replaceAll('_', ' ')}</option>)}</select>
      <select aria-label="Request type" value={filters.request_type} onChange={e => update('request_type', e.target.value)}><option value="">All types</option>{['BUG', 'CHANGE', 'FEATURE', 'SUPPORT'].map(x => <option key={x} value={x}>{x}</option>)}</select>
      <select aria-label="Priority" value={filters.priority} onChange={e => update('priority', e.target.value)}><option value="">All priorities</option>{['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map(x => <option key={x} value={x}>{x}</option>)}</select>
    </div>
    {issues.isError && <p className="alert error">{issues.error.message}</p>}
    <div className="card table-wrap"><table><thead><tr><th>Reference</th><th>Title</th><th>Type</th><th>Priority</th><th>Status</th><th>Created</th></tr></thead><tbody>
      {(issues.data ?? []).map((issue: Issue) => <tr key={issue.id}><td><Link to={`/issues/${issue.id}`}>{issue.reference}</Link></td><td>{issue.title || 'Untitled draft'}</td><td>{issue.request_type || '—'}</td><td>{issue.priority || '—'}</td><td>{issue.status}</td><td>{new Date(issue.created_at).toLocaleDateString()}</td></tr>)}
    </tbody></table>{issues.data?.length === 0 && <p className="muted">No requests match these filters.</p>}</div>
  </section>;
}

const blank: Draft = { title: '', description: '', request_type: 'SUPPORT', product: null, module: null, priority: 'MEDIUM', environment: '', steps_to_reproduce: '', expected_result: '', actual_result: '', related_request: null };

export function IssueDraftPage({ me }: { me: PortalUser }) {
  const params = useParams();
  const id = Number(params.id);
  const editing = Number.isInteger(id) && id > 0;
  const issue = useIssue(editing ? id : 0);
  const products = useProducts();
  const related = useIssues({ status: 'SUBMITTED', request_type: '', priority: '', search: '' });
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [changes, setChanges] = useState<{ id: number; version?: number; values: Partial<Draft> }>({ id, values: {} });
  const row = issue.data;
  const initial: Draft = editing && row ? { title: row.title, description: row.description, request_type: row.request_type || 'SUPPORT', product: row.product, module: row.module, priority: row.priority || 'MEDIUM', environment: row.environment, steps_to_reproduce: row.steps_to_reproduce, expected_result: row.expected_result, actual_result: row.actual_result, related_request: row.related_request } : blank;
  const values = changes.id === id ? changes.values : {};
  const draft = { ...initial, ...values };
  const save = useMutation({
    mutationFn: async () => {
      if (editing) {
        if (!row) throw new Error('Request version is unavailable. Reload this request.');
        const body = { ...draft, version: changes.version ?? row.version };
        const { data, error, response } = await api.PATCH('/api/issues/{id}/', { params: { path: { id } }, body });
        if (response.status === 409) throw new Error('This request was changed by someone else — reload');
        if (!data) throw new Error(errorMessage(error));
        return data;
      }
      const { data, error } = await api.POST('/api/issues/', { body: draft });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
    onSuccess: row => { qc.invalidateQueries({ queryKey: ISSUE_KEY }); navigate(`/issues/${row.id}`); },
  });
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setChanges({ id, version: changes.version ?? row?.version, values: { ...values, [key]: value } });
  const selected = (products.data ?? []).find((p: Product) => p.id === draft.product);
  if (!hasRole(me, 'ISSUE_OFFICER')) return <p className="alert error">Issue Officer role required.</p>;
  if (editing && issue.isPending) return <p>Loading draft…</p>;
  if (editing && (issue.isError || issue.data?.status !== 'DRAFT' || issue.data.created_by !== me.id)) return <p className="alert error">Draft unavailable.</p>;
  return <section className="stack"><div className="page-head"><div><h1>{editing ? `Edit ${issue.data?.reference}` : 'New draft'}</h1><p className="muted">Save your draft, then submit it from its detail page.</p></div></div>
    <form className="card form-grid" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
      <label>Title<input maxLength={200} value={draft.title ?? ''} onChange={e => set('title', e.target.value)} /></label>
      <label>Description<textarea value={draft.description ?? ''} onChange={e => set('description', e.target.value)} /></label>
      <label>Type<select value={draft.request_type ?? ''} onChange={e => set('request_type', e.target.value as Draft['request_type'])}>{['BUG', 'CHANGE', 'FEATURE', 'SUPPORT'].map(x => <option key={x} value={x}>{x}</option>)}</select></label>
      <label>Priority<select value={draft.priority ?? ''} onChange={e => set('priority', e.target.value as Draft['priority'])}>{['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map(x => <option key={x} value={x}>{x}</option>)}</select></label>
      <label>Product<select value={draft.product ?? ''} onChange={e => { setChanges({ id, version: changes.version ?? row?.version, values: { ...values, product: e.target.value ? Number(e.target.value) : null, module: null } }); }}><option value="">Select product</option>{(products.data ?? []).map((p: Product) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
      <label>Module<select value={draft.module ?? ''} onChange={e => set('module', e.target.value ? Number(e.target.value) : null)}><option value="">No module</option>{selected?.modules.filter(m => m.is_active).map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
      <label>Related request<select value={draft.related_request ?? ''} onChange={e => set('related_request', e.target.value ? Number(e.target.value) : null)}><option value="">None</option>{(related.data ?? []).filter((r: Issue) => r.id !== id).map((r: Issue) => <option key={r.id} value={r.id}>{r.reference} — {r.title}</option>)}</select></label>
      {draft.request_type === 'BUG' && <>
        <label>Environment<textarea value={draft.environment ?? ''} onChange={e => set('environment', e.target.value)} /></label>
        <label>Steps to reproduce<textarea value={draft.steps_to_reproduce ?? ''} onChange={e => set('steps_to_reproduce', e.target.value)} /></label>
        <label>Expected result<textarea value={draft.expected_result ?? ''} onChange={e => set('expected_result', e.target.value)} /></label>
        <label>Actual result<textarea value={draft.actual_result ?? ''} onChange={e => set('actual_result', e.target.value)} /></label>
      </>}
      {products.isError && <p className="alert error">{products.error.message}</p>}
      {save.isError && <p className="alert error">{save.error.message}</p>}
      <button className="btn primary" disabled={save.isPending}>{save.isPending ? 'Saving…' : 'Save draft'}</button>
    </form>
  </section>;
}

export function IssueDetailPage({ me }: { me: PortalUser }) {
  const id = Number(useParams().id);
  const issue = useIssue(id);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const submit = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST('/api/issues/{id}/submit/', { params: { path: { id } } });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ISSUE_KEY }),
  });
  const remove = useMutation({
    mutationFn: async () => {
      const { response, error } = await api.DELETE('/api/issues/{id}/', { params: { path: { id } } });
      if (!response.ok) throw new Error(errorMessage(error));
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ISSUE_KEY }); navigate('/issues'); },
  });
  if (!Number.isInteger(id) || id <= 0) return <p className="alert error">Request unavailable.</p>;
  if (issue.isPending) return <p>Loading request…</p>;
  if (issue.isError || !issue.data) return <p className="alert error">{issue.error?.message ?? 'Request unavailable'}</p>;
  const row = issue.data;
  const canEdit = row.status === 'DRAFT' && hasRole(me, 'ISSUE_OFFICER') && row.created_by === me.id;
  return <section className="stack"><div className="page-head"><div><p className="eyebrow">{row.reference}</p><h1>{row.title || 'Untitled draft'}</h1><p className="muted">{row.status} · {row.request_type || 'Type pending'} · {row.priority || 'Priority pending'}</p></div>
    {canEdit && <div className="actions"><Link className="btn" to={`/issues/${id}/edit`}>Edit draft</Link><button className="btn primary" disabled={submit.isPending} onClick={() => submit.mutate()}>Submit request</button><button className="btn danger" disabled={remove.isPending} onClick={() => remove.mutate()}>Delete draft</button></div>}</div>
    {(submit.isError || remove.isError) && <p className="alert error">{submit.error?.message ?? remove.error?.message}</p>}
    <div className="card"><h3>Details</h3><p>{row.description || 'No description yet.'}</p>{row.request_type === 'BUG' && <dl><dt>Environment</dt><dd>{row.environment}</dd><dt>Steps to reproduce</dt><dd>{row.steps_to_reproduce}</dd><dt>Expected result</dt><dd>{row.expected_result}</dd><dt>Actual result</dt><dd>{row.actual_result}</dd></dl>}{row.related_request && <p>Related request: <Link to={`/issues/${row.related_request}`}>#{row.related_request}</Link></p>}
      <dl><dt>Tentative delivery</dt><dd>{row.tentative_delivery_date ?? (row.tentative_delivery_later ? 'To be provided later' : 'Not set')}</dd><dt>Actual delivery</dt><dd>{row.actual_delivery_at ? new Date(row.actual_delivery_at).toLocaleString() : 'Not delivered'}</dd><dt>Last status update</dt><dd>{row.last_status_at ? new Date(row.last_status_at).toLocaleString() : 'Not yet'}</dd>{row.assignee && <><dt>Assigned user</dt><dd>#{row.assignee}</dd></>}</dl>
      {row.delivery_note && <><h4>Latest delivery</h4><p>{row.delivery_note}</p><p className="muted">{row.deployment_details}</p></>}
    </div>
    <WorkflowActions issue={row} me={me} />
    <IssueCollaboration id={id} me={me} />
    <div className="card"><h3>Timeline</h3>{row.events.length === 0 && <p className="muted">No events yet.</p>}<ol>{row.events.map(event => { const details = event.details as Record<string, unknown>; return <li key={event.id}><strong>{event.kind.replaceAll('_', ' ')}</strong> · {event.from_status} → {event.to_status} · {new Date(event.created_at).toLocaleString()} · actor #{event.actor}{event.reason && <p>Reason: {event.reason}</p>}{Boolean(details.tentative_delivery_date) && <p>Tentative delivery: {String(details.tentative_delivery_date)}</p>}{details.tentative_delivery_later === true && <p>Tentative delivery: to be provided later</p>}{Boolean(details.to_date) && <p>Tentative delivery revised: {String(details.from_date ?? 'later')} → {String(details.to_date)}</p>}{details.to_later === true && <p>Tentative delivery revised: {String(details.from_date ?? 'later')} → to be provided later</p>}{Boolean(details.actual_delivery_at) && <p>Actual delivery: {new Date(String(details.actual_delivery_at)).toLocaleString()}</p>}{Boolean(details.delivery_note) && <p>Delivery: {String(details.delivery_note)}</p>}{Boolean(details.deployment_details) && <p>Version/deployment: {String(details.deployment_details)}</p>}{Boolean(details.to_assignee) && <p>Assigned user: #{String(details.to_assignee)}</p>}</li>; })}</ol></div>
  </section>;
}
