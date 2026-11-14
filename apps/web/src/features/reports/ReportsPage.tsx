import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { components } from '../../api/generated/schema';
import { errorMessage } from '../auth/hooks';
import { hasRole, type PortalUser } from '../auth/roles';

type DetailedRow = components['schemas']['DetailedReportRow'];
type Summary = components['schemas']['SummaryReport'];

function currentYear() {
  return Number(
    new Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Dhaka', year: 'numeric' }).format(
      new Date(),
    ),
  );
}

type Filters = { start: string; end: string; status: string; bank: string; overdue: boolean };

export function ReportsPage({ me }: { me: PortalUser }) {
  const year = currentYear();
  const [filters, setFilters] = useState<Filters>({
    start: `${year}-01-01`,
    end: `${year}-12-31`,
    status: '',
    bank: '',
    overdue: false,
  });
  const [exportError, setExportError] = useState('');
  const [exporting, setExporting] = useState(false);
  const [recurringOf, setRecurringOf] = useState('');
  const navigate = useNavigate();
  const staff = me.organization.kind === 'DATASOFT';
  const query = {
    start: filters.start,
    end: filters.end,
    ...(filters.status ? { status: filters.status } : {}),
    ...(staff && filters.bank ? { bank: Number(filters.bank) } : {}),
    ...(filters.overdue ? { overdue: true } : {}),
  };
  const detailed = useQuery({
    queryKey: ['report', 'detailed', query],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/reports/detailed/', { params: { query } });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
  const summary = useQuery({
    queryKey: ['report', 'summary', query],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/reports/summary/', { params: { query } });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
  const banks = useQuery({
    queryKey: ['report', 'banks'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/reports/banks/');
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
    enabled: staff,
  });
  const closedIssues = useQuery({
    queryKey: ['report', 'closed-issues'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/issues/', {
        params: { query: { status: 'CLOSED' } },
      });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
    enabled: hasRole(me, 'ISSUE_OFFICER'),
  });
  const createRecurring = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST('/api/issues/', {
        body: { recurring_of: Number(recurringOf) },
      });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
    onSuccess: (issue) => navigate(`/issues/${issue.id}/edit`),
  });
  const set = <K extends keyof Filters>(key: K, value: Filters[K]) =>
    setFilters((previous) => ({ ...previous, [key]: value }));
  async function download(kind: 'detailed' | 'summary') {
    setExportError('');
    setExporting(true);
    try {
      const params = new URLSearchParams();
      params.set('start', filters.start);
      params.set('end', filters.end);
      if (filters.status) params.set('status', filters.status);
      if (staff && filters.bank) params.set('bank', filters.bank);
      if (filters.overdue) params.set('overdue', 'true');
      const response = await fetch(`/api/reports/${kind}/csv/?${params}`, {
        credentials: 'include',
      });
      if (!response.ok) throw new Error(`Export failed (${response.status})`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${kind}-report.csv`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setExportError(error instanceof Error ? error.message : 'Export failed');
    } finally {
      setExporting(false);
    }
  }
  return (
    <section className="stack">
      <div className="page-head">
        <div>
          <h1>Reports</h1>
          <p className="muted">Requests created in the selected period.</p>
        </div>
      </div>
      {hasRole(me, 'ISSUE_OFFICER') && (
        <div className="card toolbar">
          <label>
            Previously closed request
            <select
              aria-label="Previously closed request"
              value={recurringOf}
              onChange={(e) => setRecurringOf(e.target.value)}
            >
              <option value="">Select a closed request</option>
              {closedIssues.data?.map((issue) => (
                <option key={issue.id} value={issue.id}>
                  {issue.reference} — {issue.title}
                </option>
              ))}
            </select>
          </label>
          <button
            className="btn"
            disabled={!recurringOf || createRecurring.isPending}
            onClick={() => createRecurring.mutate()}
          >
            Create recurring draft
          </button>
          {createRecurring.isError && (
            <p className="alert error">{createRecurring.error.message}</p>
          )}
        </div>
      )}
      <div className="card toolbar">
        <label>
          From
          <input
            aria-label="From"
            type="date"
            value={filters.start}
            onChange={(e) => set('start', e.target.value)}
          />
        </label>
        <label>
          Through
          <input
            aria-label="Through"
            type="date"
            value={filters.end}
            onChange={(e) => set('end', e.target.value)}
          />
        </label>
        <label>
          Status
          <select
            aria-label="Report status"
            value={filters.status}
            onChange={(e) => set('status', e.target.value)}
          >
            <option value="">All statuses</option>
            {[
              'SUBMITTED',
              'ACCEPTED',
              'REJECTED',
              'PENDING',
              'IN_PROGRESS',
              'AWAITING_VERIFICATION',
              'VERIFIED',
              'CLOSED',
            ].map((status) => (
              <option key={status} value={status}>
                {status.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </label>
        {staff && (
          <label>
            Bank
            <select
              aria-label="Report bank"
              value={filters.bank}
              onChange={(e) => set('bank', e.target.value)}
            >
              <option value="">All banks</option>
              {banks.data?.map((bank) => (
                <option key={bank.id} value={bank.id}>
                  {bank.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          <input
            type="checkbox"
            checked={filters.overdue}
            onChange={(e) => set('overdue', e.target.checked)}
          />{' '}
          Overdue only
        </label>
      </div>
      {(detailed.isError || summary.isError || banks.isError || exportError) && (
        <p className="alert error" role="alert">
          {detailed.error?.message ?? summary.error?.message ?? banks.error?.message ?? exportError}
        </p>
      )}
      <div className="card">
        <div className="page-head">
          <h2>Summary</h2>
          <button className="btn" disabled={exporting} onClick={() => download('summary')}>
            Export CSV
          </button>
        </div>
        {summary.isPending ? (
          <p>Loading summary…</p>
        ) : (
          summary.data && <SummaryView summary={summary.data} />
        )}
      </div>
      <div className="card table-wrap">
        <div className="page-head">
          <h2>Detailed report</h2>
          <button className="btn" disabled={exporting} onClick={() => download('detailed')}>
            Export CSV
          </button>
        </div>
        {detailed.isPending ? (
          <p>Loading details…</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Reference ID</th>
                <th>Bank</th>
                <th>Issue Officer</th>
                <th>Title</th>
                <th>Issue detail</th>
                <th>Status</th>
                <th>Created</th>
                <th>Submitted</th>
                <th>Tentative delivery</th>
                <th>Actual delivery</th>
                <th>Last status update</th>
                <th>Closed</th>
              </tr>
            </thead>
            <tbody>
              {(detailed.data ?? []).map((row: DetailedRow) => (
                <tr key={row.id}>
                  <td>
                    <Link to={`/issues/${row.id}`}>{row.reference_id}</Link>
                  </td>
                  <td>{row.bank}</td>
                  <td>{row.issue_officer}</td>
                  <td>{row.title}</td>
                  <td>{row.issue_detail}</td>
                  <td>
                    {row.status}{' '}
                    {row.is_overdue && <strong className="alert error">Overdue</strong>}
                  </td>
                  <td>{row.creation_date}</td>
                  <td>{row.submission_date ?? '—'}</td>
                  <td>{row.tentative_delivery_date ?? '—'}</td>
                  <td>{row.actual_delivery_date ?? '—'}</td>
                  <td>{row.last_status_update_date ?? '—'}</td>
                  <td>{row.closure_date ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {detailed.data?.length === 0 && <p className="muted">No requests match these filters.</p>}
      </div>
    </section>
  );
}

function SummaryView({ summary }: { summary: Summary }) {
  return (
    <div className="stack">
      <div className="grid">
        <div>
          <strong>Total requests</strong>
          <p>{summary.total}</p>
        </div>
        <div>
          <strong>Reopened</strong>
          <p>{summary.reopened_count}</p>
        </div>
        <div>
          <strong>Recurring</strong>
          <p>{summary.recurring_count}</p>
        </div>
      </div>
      <div className="grid">
        <Breakdown title="By status" values={summary.by_status} />
        <Breakdown title="By month" values={summary.by_month} />
        {summary.by_bank != null && <Breakdown title="By bank" values={summary.by_bank} />}
      </div>
    </div>
  );
}

function Breakdown({ title, values }: { title: string; values: Record<string, number> }) {
  return (
    <div>
      <h3>{title}</h3>
      <table>
        <tbody>
          {Object.entries(values).map(([label, count]) => (
            <tr key={label}>
              <th>{label.replaceAll('_', ' ')}</th>
              <td>{count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function IssueReportSignals() {
  const id = Number(useParams().id);
  const issue = useQuery({
    queryKey: ['issues', id],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/issues/{id}/', { params: { path: { id } } });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
    enabled: Number.isInteger(id) && id > 0,
  });
  if (!issue.data) return null;
  const row = issue.data;
  if (!row.is_overdue && !row.recurring_of && row.recurring_requests.length === 0) return null;
  return (
    <div className="card">
      {row.is_overdue && (
        <strong className="alert error">Overdue: tentative delivery date has passed.</strong>
      )}
      {row.recurring_of && (
        <p>
          Recurring of <Link to={`/issues/${row.recurring_of}`}>request #{row.recurring_of}</Link>
        </p>
      )}
      {row.recurring_requests.length > 0 && (
        <p>
          Recurring requests:{' '}
          {row.recurring_requests.map((child) => (
            <span key={child}>
              <Link to={`/issues/${child}`}>#{child}</Link>{' '}
            </span>
          ))}
        </p>
      )}
    </div>
  );
}
