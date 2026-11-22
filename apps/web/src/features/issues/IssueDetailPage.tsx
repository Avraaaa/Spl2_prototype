import { useState, type ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { components } from '../../api/generated/schema';
import { errorMessage } from '../auth/hooks';
import { isStaff } from '../auth/nav';
import { hasRole, type PortalUser } from '../auth/roles';
import { IssueReportSignals } from '../reports/ReportsPage';
import { EmptyState, ErrorState, LoadingState } from '../ui/EmptyState';
import { StatusBadge } from '../ui/StatusBadge';
import { formatDateTime } from '../ui/format';
import { priorityLabel, typeLabel } from '../ui/labels';
import { WorkflowActions } from '../workflow/WorkflowActions';
import { AttachmentsPanel, CommentsPanel } from './IssueCollaboration';
import { InternalSection } from './InternalSection';
import { deliverySummary } from './delivery';
import { ISSUE_KEY, useIssue } from './hooks';
import { eventLines, eventTitle } from './timeline';
import { canRequestOriginalText, originalTextAction, type OriginalTextState } from './originalText';

type Issue = components['schemas']['Issue'];

function Facts({ children }: { children: ReactNode }) {
  return <dl className="facts">{children}</dl>;
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="fact">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function Details({ row }: { row: Issue }) {
  return (
    <section className="card stack" aria-label="Details">
      <h3>Details</h3>
      <p className="prewrap">{row.description || 'No description yet.'}</p>
      {row.confirmed_label && <p><strong>Confirmed label:</strong> <span className="chip">{row.confirmed_label.name}</span></p>}
      {row.request_type === 'BUG' && (
        <Facts>
          <Fact label="Environment">{row.environment || '—'}</Fact>
          <Fact label="Steps to reproduce">{row.steps_to_reproduce || '—'}</Fact>
          <Fact label="Expected result">{row.expected_result || '—'}</Fact>
          <Fact label="Actual result">{row.actual_result || '—'}</Fact>
        </Facts>
      )}
      {row.related_request && (
        <p>
          Related request:{' '}
          <Link to={`/issues/${row.related_request}`}>
            {row.related_request_reference} — {row.related_request_title}
          </Link>
        </p>
      )}
      {row.recurring_of && (
        <p>
          Recurring of:{' '}
          <Link to={`/issues/${row.recurring_of}`}>
            {row.recurring_of_reference} — {row.recurring_of_title}
          </Link>
        </p>
      )}
    </section>
  );
}

function Delivery({ row }: { row: Issue }) {
  const tentative = row.tentative_delivery_date ?? (row.tentative_delivery_later ? 'To be provided later' : 'Not set');
  return (
    <section className="card stack" aria-label="Delivery info">
      <h3>Delivery info</h3>
      <Facts>
        <Fact label="Tentative delivery">{tentative}</Fact>
        <Fact label="Actual delivery">{deliverySummary(row)}</Fact>
        <Fact label="Assigned to">{row.assignee_name ?? 'Not assigned'}</Fact>
        <Fact label="Last status update">{row.last_status_at ? formatDateTime(row.last_status_at) : 'Not yet'}</Fact>
      </Facts>
      {row.acceptance_criteria && (
        <div className="acceptance-criteria" aria-label="Acceptance criteria">
          <h4>Agreed acceptance criteria</h4>
          <p className="prewrap">{row.acceptance_criteria}</p>
        </div>
      )}
      {row.delivery_note && (
        <div>
          <h4>Latest delivery note</h4>
          <p className="prewrap">{row.delivery_note}</p>
          {row.deployment_details && <p className="muted prewrap">{row.deployment_details}</p>}
        </div>
      )}
    </section>
  );
}

function Timeline({ row }: { row: Issue }) {
  return (
    <section className="card stack" aria-label="Timeline">
      <h3>Timeline</h3>
      {row.events.length === 0 && <EmptyState>No events yet.</EmptyState>}
      <ol className="timeline">
        {row.events.map(event => (
          <li key={event.id}>
            <strong>{eventTitle(event)}</strong>
            <span className="muted">
              {' '}
              · {event.actor_name} · {formatDateTime(event.created_at ?? null)}
            </span>
            {eventLines(event).map(line => (
              <p key={line} className="timeline-line">
                {line}
              </p>
            ))}
          </li>
        ))}
      </ol>
    </section>
  );
}

function DuplicateReview({ row, me }: { row: Issue; me: PortalUser }) {
  const qc = useQueryClient();
  const candidates = useQuery({
    queryKey: ['duplicate-candidates', row.id],
    enabled: isStaff(me),
    queryFn: async () => {
      const { data, error } = await api.GET('/api/search/duplicate-candidates/{issue_id}/', { params: { path: { issue_id: row.id } } });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
  const review = useMutation({
    mutationFn: async ({ candidateIssue, decision }: { candidateIssue: number; decision: 'confirmed' | 'recurring' | 'dismissed' }) => {
      const { data, error } = await api.POST('/api/search/duplicate-reviews/', {
        body: { issue: row.id, candidate_issue: candidateIssue, decision },
      });
      if (!data) throw new Error(errorMessage(error));
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['duplicate-candidates', row.id] }); qc.invalidateQueries({ queryKey: ISSUE_KEY }); },
  });
  if (!isStaff(me)) return null;
  const duplicates = candidates.data?.duplicates ?? [];
  return (
    <section className="card stack" aria-label="Possible duplicate review">
      <div><h3>Possible duplicates</h3><p className="muted small">Review same-bank matches. Nothing is merged automatically.</p></div>
      {candidates.isPending && <p className="muted small">Checking similar requests…</p>}
      {candidates.isError && <p className="alert error small">Duplicate suggestions are unavailable.</p>}
      {!candidates.isPending && duplicates.length === 0 && <p className="muted small">No likely duplicate found.</p>}
      {duplicates.map(candidate => {
        if (typeof candidate.id !== 'number' || typeof candidate.title !== 'string') return null;
        const closed = candidate.status === 'CLOSED';
        return (
          <div className="suggestion-row" key={candidate.id}>
            <span><strong>{typeof candidate.reference === 'string' ? candidate.reference : `Request ${candidate.id}`}</strong> · {candidate.title}</span>
            <span className="actions">
              <button className="btn small" disabled={review.isPending} onClick={() => review.mutate({ candidateIssue: candidate.id as number, decision: 'confirmed' })}>Confirm</button>
              {closed && <button className="btn small" disabled={review.isPending} onClick={() => review.mutate({ candidateIssue: candidate.id as number, decision: 'recurring' })}>Recurring</button>}
              <button className="btn small ghost" disabled={review.isPending} onClick={() => review.mutate({ candidateIssue: candidate.id as number, decision: 'dismissed' })}>Dismiss</button>
            </span>
          </div>
        );
      })}
      {review.isError && <p className="alert error small">{review.error.message}</p>}
    </section>
  );
}

function DraftActions({ row }: { row: Issue }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [comment, setComment] = useState('');
  const submit = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST('/api/issues/{id}/submit/', { params: { path: { id: row.id } }, body: { comment } });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ISSUE_KEY });
      qc.invalidateQueries({ queryKey: ['report'] });
    },
  });
  const remove = useMutation({
    mutationFn: async () => {
      const { response, error } = await api.DELETE('/api/issues/{id}/', { params: { path: { id: row.id } } });
      if (!response.ok) throw new Error(errorMessage(error));
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ISSUE_KEY });
      qc.invalidateQueries({ queryKey: ['report'] });
      navigate('/issues');
    },
  });
  return (
    <div className="stack">
      <p className="muted">This draft has not been submitted yet.</p>
      <Link className="btn" to={`/issues/${row.id}/edit`}>
        Edit draft
      </Link>
      <label>Comment (optional)<textarea rows={2} value={comment} onChange={event => setComment(event.target.value)} maxLength={5000} /></label>
      <button className="btn primary" disabled={submit.isPending} onClick={() => submit.mutate()}>
        Submit request
      </button>
      <button className="btn danger" disabled={remove.isPending} onClick={() => remove.mutate()}>
        Delete draft
      </button>
      {submit.isError && <ErrorState error={submit.error} />}
      {remove.isError && <ErrorState error={remove.error} />}
    </div>
  );
}

function NextAction({ row, me }: { row: Issue; me: PortalUser }) {
  const isDraft = row.status === 'DRAFT';
  const ownDraft = isDraft && hasRole(me, 'ISSUE_OFFICER') && row.created_by === me.id;
  return (
    <aside className="card stack" aria-label="Next action">
      <h3>Next action</h3>
      {ownDraft ? <DraftActions row={row} /> : <WorkflowActions key={`${row.id}-${row.version}`} issue={row} me={me} />}
    </aside>
  );
}

type Tab = 'comments' | 'attachments';

function Conversation({ id, me }: { id: number; me: PortalUser }) {
  const [tab, setTab] = useState<Tab>('comments');
  return (
    <section className="card stack" aria-label="Comments and attachments">
      <div className="tabs" role="tablist">
        {(['comments', 'attachments'] as const).map(name => (
          <button
            key={name}
            role="tab"
            aria-selected={tab === name}
            className={tab === name ? 'tab active' : 'tab'}
            onClick={() => setTab(name)}
          >
            {name === 'comments' ? 'Comments' : 'Attachments'}
          </button>
        ))}
      </div>
      {tab === 'comments' ? <CommentsPanel id={id} me={me} /> : <AttachmentsPanel id={id} me={me} />}
    </section>
  );
}

export function IssueDetailPage({ me }: { me: PortalUser }) {
  const id = Number(useParams().id);
  const issue = useIssue(id);
  if (!Number.isInteger(id) || id <= 0) return <p className="alert error">Request unavailable.</p>;
  if (issue.isPending) return <LoadingState label="Loading request…" />;
  if (issue.isError || !issue.data) return <ErrorState error={issue.error ?? new Error('Request unavailable')} />;
  const row = issue.data;
  const staff = isStaff(me);
  const canViewOriginal = me.can_view_unmasked_original;
  return (
    <section className="stack">
      <header className="issue-head card">
        <p className="eyebrow">{row.reference ?? 'Draft'}</p>
        <h1>{row.title || 'Untitled draft'}</h1>
        <div className="meta">
          <StatusBadge status={row.status} />
          <span>{row.organization_name}</span>
          <span>{priorityLabel(row.priority)} priority</span>
          <span>{typeLabel(row.request_type)}</span>
          <span className="muted">Created by {row.created_by_name}</span>
        </div>
        {canViewOriginal && <OriginalTextButton id={id} />}
      </header>
      <IssueReportSignals />
      <div className="detail-layout">
        <div className="stack main-col">
          <Details row={row} />
          <DuplicateReview row={row} me={me} />
          <Delivery row={row} />
          <Timeline row={row} />
          <Conversation id={id} me={me} />
          {staff && <InternalSection id={id} me={me} />}
        </div>
        <div className="side-col">
          <NextAction row={row} me={me} />
        </div>
      </div>
    </section>
  );
}

function OriginalTextButton({ id }: { id: number }) {
  const [state, setState] = useState<OriginalTextState>('hidden');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [original, setOriginal] = useState<components['schemas']['IssueOriginalResponse'] | null>(null);
  const loadOriginal = async () => {
    if (!canRequestOriginalText(state)) return;
    setLoading(true);
    setError('');
    const { data, error: apiError } = await api.GET('/api/issues/{id}/original/', { params: { path: { id } } });
    setLoading(false);
    if (!data) {
      setError(errorMessage(apiError));
      return;
    }
    setOriginal(data);
    setState(current => originalTextAction(current, 'reveal'));
  };
  return (
    <div className="stack original-review">
      {state === 'hidden' && <button className="btn small" type="button" onClick={() => setState(originalTextAction(state, 'show'))}>Show original</button>}
      {state === 'confirm' && <div className="alert info" role="group" aria-label="Confirm original text access">
        <p>Original text may contain sensitive information. Access is recorded. Continue?</p>
        <button className="btn small" type="button" onClick={() => setState(originalTextAction(state, 'cancel'))}>Cancel</button>
        <button className="btn small primary" type="button" onClick={() => void loadOriginal()} disabled={loading}>{loading ? 'Loading original…' : 'Continue'}</button>
      </div>}
      {error && <p role="alert" className="alert error">{error}</p>}
      {state === 'revealed' && original && <aside className="alert info"><strong>Original text</strong><p>{original.title}</p><p className="prewrap">{original.description}</p><button className="btn small" type="button" onClick={() => { setOriginal(null); setState(originalTextAction(state, 'hide')); }}>Hide original</button></aside>}
    </div>
  );
}
