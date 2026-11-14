import { useState } from 'react';
import { Link } from 'react-router-dom';
import { hasRole, type PortalUser } from '../auth/roles';
import { isStaff } from '../auth/nav';
import { EmptyState, ErrorState, LoadingState } from '../ui/EmptyState';
import { PageHeader } from '../ui/PageHeader';
import { StatusBadge } from '../ui/StatusBadge';
import { formatDate } from '../ui/format';
import { PRIORITY_CODES, priorityLabel, STATUS_CODES, statusLabel, TYPE_CODES, typeLabel } from '../ui/labels';
import { useBanks, useIssues, type IssueFilters } from './hooks';

export type ListMode = 'all' | 'queue' | 'mine' | 'awaiting';

const MODES: Record<ListMode, { title: string; subtitle: string; fixed: IssueFilters; empty: string }> = {
  all: { title: 'Requests', subtitle: 'All requests you can see.', fixed: {}, empty: 'No requests match these filters.' },
  queue: {
    title: 'Intake queue',
    subtitle: 'Submitted requests waiting for a decision, oldest first.',
    fixed: { status: 'SUBMITTED', ordering: 'oldest' },
    empty: 'The intake queue is empty.',
  },
  mine: {
    title: 'My work',
    subtitle: 'Requests assigned to you.',
    fixed: { assignee: 'me' },
    empty: 'Nothing is assigned to you.',
  },
  awaiting: {
    title: 'Awaiting my verification',
    subtitle: 'Delivered requests that need your verification.',
    fixed: { status: 'AWAITING_VERIFICATION' },
    empty: 'Nothing is waiting for verification.',
  },
};

export function IssueListPage({ me, mode = 'all' }: { me: PortalUser; mode?: ListMode }) {
  const config = MODES[mode];
  const staff = isStaff(me);
  const [filters, setFilters] = useState({ status: '', request_type: '', priority: '', search: '', organization: '' });
  const fixed = config.fixed;
  const issues = useIssues({ ...filters, ...fixed, status: fixed.status ?? filters.status });
  const banks = useBanks(staff);
  const officer = hasRole(me, 'ISSUE_OFFICER');
  const update = (name: keyof typeof filters, value: string) => setFilters(f => ({ ...f, [name]: value }));
  const showStatusFilter = mode === 'all' || mode === 'mine';

  return (
    <section className="stack">
      <PageHeader
        title={config.title}
        subtitle={config.subtitle}
        actions={
          officer && mode === 'all' ? (
            <Link className="btn primary" to="/issues/new">
              New request
            </Link>
          ) : undefined
        }
      />
      <div className="card toolbar">
        <input
          aria-label="Search title or reference"
          placeholder="Search title or reference"
          value={filters.search}
          onChange={e => update('search', e.target.value)}
        />
        {staff && (
          <select aria-label="Bank" value={filters.organization} onChange={e => update('organization', e.target.value)}>
            <option value="">All banks</option>
            {(banks.data ?? []).map(bank => (
              <option key={bank.id} value={bank.id}>
                {bank.name}
              </option>
            ))}
          </select>
        )}
        {showStatusFilter && (
          <select aria-label="Status" value={filters.status} onChange={e => update('status', e.target.value)}>
            <option value="">All statuses</option>
            {STATUS_CODES.filter(code => staff ? code !== 'DRAFT' : true).map(code => (
              <option key={code} value={code}>
                {statusLabel(code)}
              </option>
            ))}
          </select>
        )}
        <select aria-label="Request type" value={filters.request_type} onChange={e => update('request_type', e.target.value)}>
          <option value="">All types</option>
          {TYPE_CODES.map(code => (
            <option key={code} value={code}>
              {typeLabel(code)}
            </option>
          ))}
        </select>
        <select aria-label="Priority" value={filters.priority} onChange={e => update('priority', e.target.value)}>
          <option value="">All priorities</option>
          {PRIORITY_CODES.map(code => (
            <option key={code} value={code}>
              {priorityLabel(code)}
            </option>
          ))}
        </select>
      </div>
      {issues.isPending && <LoadingState label="Loading requests…" />}
      {issues.isError && <ErrorState error={issues.error} />}
      {issues.data && issues.data.length === 0 && <EmptyState>{config.empty}</EmptyState>}
      {issues.data && issues.data.length > 0 && (
        <div className="card table-wrap">
          <table>
            <thead>
              <tr>
                <th>Reference</th>
                {staff && <th>Bank</th>}
                <th>Title</th>
                <th>Type</th>
                <th>Priority</th>
                <th>Status</th>
                {staff && <th>Assigned to</th>}
                <th>{mode === 'queue' ? 'Submitted' : 'Created'}</th>
              </tr>
            </thead>
            <tbody>
              {issues.data.map(issue => (
                <tr key={issue.id}>
                  <td>
                    <Link to={`/issues/${issue.id}`}>{issue.reference ?? 'Draft'}</Link>
                  </td>
                  {staff && <td>{issue.organization_name}</td>}
                  <td>{issue.title || 'Untitled draft'}</td>
                  <td>{typeLabel(issue.request_type)}</td>
                  <td>{priorityLabel(issue.priority)}</td>
                  <td>
                    <StatusBadge status={issue.status} />
                  </td>
                  {staff && <td>{issue.assignee_name ?? '—'}</td>}
                  <td>{formatDate((mode === 'queue' ? issue.submitted_at : issue.created_at) ?? null)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
