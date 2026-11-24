import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { components } from '../../api/generated/schema';
import { errorMessage } from '../auth/hooks';
import { isStaff } from '../auth/nav';
import { hasRole, roleLabel, type PortalUser } from '../auth/roles';
import { useIssues, type IssueFilters } from '../issues/hooks';
import { EmptyState, ErrorState, LoadingState } from '../ui/EmptyState';
import { PageHeader } from '../ui/PageHeader';
import { StatusBadge } from '../ui/StatusBadge';
import { ColorChip } from '../ui/ColorChip';
import { formatDate } from '../ui/format';
import { statusLabel, typeLabel } from '../ui/labels';
import { useDisplayColors } from '../ui/useDisplayColors';

type Counts = components['schemas']['DashboardCounts'];

function useDashboardCounts() {
  return useQuery({
    queryKey: ['report', 'dashboard'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/reports/dashboard/');
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
}

function Stat({ label, value, tone }: { label: string; value: number | undefined; tone?: string }) {
  return (
    <div className={`stat ${tone ?? ''}`}>
      <strong>{value ?? '—'}</strong>
      <span>{label}</span>
    </div>
  );
}

type ListProps = {
  title: string;
  filters: IssueFilters;
  empty: string;
  to?: string;
  showBank?: boolean;
  limit?: number;
};

/** A short action list backed by the real request list endpoint. */
function ActionList({ title, filters, empty, to, showBank, limit = 5 }: ListProps) {
  const colors = useDisplayColors();
  const issues = useIssues(filters);
  const rows = (issues.data ?? []).slice(0, limit);
  return (
    <section className="card stack" aria-label={title}>
      <div className="list-head">
        <h3>
          {title}
          {issues.data ? <span className="count-pill">{issues.data.length}</span> : null}
        </h3>
        {to && <Link to={to}>View all</Link>}
      </div>
      {issues.isPending && <LoadingState />}
      {issues.isError && <ErrorState error={issues.error} />}
      {issues.data && rows.length === 0 && <EmptyState>{empty}</EmptyState>}
      <ul className="mini-list">
        {rows.map(issue => (
          <li key={issue.id}>
            <Link to={`/issues/${issue.id}`}>
              <strong>{issue.reference ?? 'Draft'}</strong> {issue.title || 'Untitled draft'}
            </Link>
            <span className="muted">
              {showBank ? `${issue.organization_name} · ` : ''}
              {formatDate(issue.updated_at ?? null)}
            </span>
            <StatusBadge status={issue.status} />
            <ColorChip color={colors.data?.request_types[issue.request_type ?? '']}>
              {typeLabel(issue.request_type)}
            </ColorChip>
            {issue.product_name && (
              <ColorChip color={colors.data?.products[String(issue.product)]}>
                {issue.product_name}
              </ColorChip>
            )}
            {issue.confirmed_label && (
              <ColorChip color={colors.data?.labels[String(issue.confirmed_label.id)]}>
                {issue.confirmed_label.name}
              </ColorChip>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function CountsCard({ counts }: { counts: Counts }) {
  const entries = Object.entries(counts.by_status).filter(([, count]) => count > 0);
  return (
    <section className="card stack" aria-label="Request counts">
      <h3>Requests by status</h3>
      <div className="stats">
        <Stat label="Total" value={counts.total} />
        {entries.map(([status, count]) => (
          <Stat key={status} label={statusLabel(status)} value={count} />
        ))}
      </div>
    </section>
  );
}

function BankCounts({ counts }: { counts: Counts }) {
  const banks = Object.entries(counts.by_bank ?? {});
  return (
    <section className="card stack" aria-label="Requests per bank">
      <h3>Requests per bank</h3>
      {banks.length === 0 && <EmptyState>No submitted requests yet.</EmptyState>}
      <ul className="mini-list">
        {banks.map(([bank, count]) => (
          <li key={bank}>
            <span>{bank}</span>
            <strong>{count}</strong>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ClientDashboard({ me, counts }: { me: PortalUser; counts: Counts | undefined }) {
  const officer = hasRole(me, 'ISSUE_OFFICER');
  const verifier = hasRole(me, 'ISSUE_VERIFIER');
  const recent = useIssues({});
  const recentRows = [...(recent.data ?? [])]
    .filter(issue => issue.status !== 'DRAFT')
    .sort((a, b) => (b.updated_at ?? '').localeCompare(a.updated_at ?? ''))
    .slice(0, 5);
  return (
    <>
      {counts && <CountsCard counts={counts} />}
      <div className="grid">
        {officer && (
          <ActionList title="My drafts" filters={{ status: 'DRAFT' }} empty="You have no drafts." to="/issues" />
        )}
        {verifier && (
          <ActionList
            title="Awaiting my verification"
            filters={{ status: 'AWAITING_VERIFICATION' }}
            empty="Nothing is waiting for verification."
            to="/awaiting"
          />
        )}
        <section className="card stack" aria-label="Recently updated">
          <div className="list-head">
            <h3>Recently updated</h3>
            <Link to="/issues">View all</Link>
          </div>
          {recent.isPending && <LoadingState />}
          {recent.isError && <ErrorState error={recent.error} />}
          {recent.data && recentRows.length === 0 && <EmptyState>No requests yet.</EmptyState>}
          <ul className="mini-list">
            {recentRows.map(issue => (
              <li key={issue.id}>
                <Link to={`/issues/${issue.id}`}>
                  <strong>{issue.reference}</strong> {issue.title}
                </Link>
                <span className="muted">{formatDate(issue.updated_at ?? null)}</span>
                <StatusBadge status={issue.status} />
              </li>
            ))}
          </ul>
        </section>
      </div>
      {officer && (
        <div>
          <Link className="btn primary" to="/issues/new">
            New request
          </Link>
        </div>
      )}
    </>
  );
}

function ConsoleDashboard({ counts }: { counts: Counts | undefined }) {
  return (
    <>
      <div className="stats">
        <Stat label="Intake queue" value={counts?.pending_intake} tone="tone-info" />
        <Stat label="Overdue" value={counts?.overdue} tone="tone-danger" />
        <Stat label="Awaiting verification" value={counts?.by_status.AWAITING_VERIFICATION} tone="tone-warn" />
        <Stat label="Delivered (30 days)" value={counts?.recent_deliveries} tone="tone-ok" />
      </div>
      <div className="grid">
        <ActionList
          title="Intake queue"
          filters={{ status: 'SUBMITTED', ordering: 'oldest' }}
          empty="No requests are waiting for intake."
          to="/queue"
          showBank
        />
        <ActionList title="Overdue" filters={{ overdue: true }} empty="Nothing is overdue." to="/issues" showBank />
        <ActionList
          title="Awaiting verification"
          filters={{ status: 'AWAITING_VERIFICATION' }}
          empty="Nothing is awaiting client verification."
          to="/issues"
          showBank
        />
        <ActionList title="My assignments" filters={{ assignee: 'me' }} empty="Nothing is assigned to you." to="/my-work" showBank />
      </div>
      {counts && <BankCounts counts={counts} />}
    </>
  );
}

export function Dashboard({ me }: { me: PortalUser }) {
  const counts = useDashboardCounts();
  const staff = isStaff(me);
  return (
    <section className="stack">
      <PageHeader
        eyebrow={staff ? 'DATASOFT CONSOLE' : 'CLIENT PORTAL'}
        title={`Welcome, ${me.full_name.split(' ')[0]}`}
        subtitle={`${me.organization.name} · ${me.roles.map(roleLabel).join(' + ')}`}
      />
      {counts.isError && <ErrorState error={counts.error} />}
      {counts.isPending && <LoadingState label="Loading counts…" />}
      {staff ? <ConsoleDashboard counts={counts.data} /> : <ClientDashboard me={me} counts={counts.data} />}
    </section>
  );
}
