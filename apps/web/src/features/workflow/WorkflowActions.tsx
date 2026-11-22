import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { components } from '../../api/generated/schema';
import { errorMessage } from '../auth/hooks';
import { hasRole, type PortalUser } from '../auth/roles';

type Issue = components['schemas']['Issue'];
type Action = 'accept' | 'reject' | 'revise-date' | 'assign' | 'start' | 'deliver' | 'verify' | 'fail-verification' | 'close' | 'reopen';

const LABEL: Record<Action, string> = {
  accept: 'Accept', reject: 'Reject', 'revise-date': 'Revise tentative date',
  assign: 'Assign or reassign', start: 'Start work', deliver: 'Deliver',
  verify: 'Verify', 'fail-verification': 'Fail verification', close: 'Close', reopen: 'Reopen',
};

export function availableActions(issue: Pick<Issue, 'status'>, me: PortalUser): Action[] {
  const staff = hasRole(me, 'SUPPORT_AGENT') || hasRole(me, 'DATASOFT_ADMIN');
  const verifier = hasRole(me, 'ISSUE_VERIFIER');
  switch (issue.status) {
    case 'SUBMITTED': return staff ? ['accept', 'reject'] : [];
    case 'ACCEPTED': return staff ? ['assign', 'revise-date'] : [];
    case 'PENDING': return staff ? ['start', 'assign', 'revise-date'] : [];
    case 'IN_PROGRESS': return staff ? ['deliver', 'assign', 'revise-date'] : [];
    case 'AWAITING_VERIFICATION': return verifier ? ['verify', 'fail-verification'] : [];
    case 'VERIFIED': return staff ? ['close'] : [];
    case 'CLOSED': return staff || verifier || hasRole(me, 'ISSUE_OFFICER') ? ['reopen'] : [];
    default: return [];
  }
}

function requireIssue(data: Issue | undefined, error: unknown, status: number): Issue {
  if (status === 409) throw new Error('This request was changed by someone else — reload');
  if (!data) throw new Error(errorMessage(error));
  return data;
}

export function WorkflowActions({ issue, me }: { issue: Issue; me: PortalUser }) {
  const actions = availableActions(issue, me);
  const staff = hasRole(me, 'SUPPORT_AGENT') || hasRole(me, 'DATASOFT_ADMIN');
  const assignees = useQuery({
    queryKey: ['workflow', 'assignees'],
    enabled: staff,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/issues/assignees/');
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
  const [choice, setChoice] = useState<Action>('accept');
  const [date, setDate] = useState(issue.tentative_delivery_date ?? '');
  const [later, setLater] = useState(issue.tentative_delivery_later ?? false);
  const [reason, setReason] = useState('');
  const [comment, setComment] = useState('');
  const [assignee, setAssignee] = useState(issue.assignee?.toString() ?? '');
  const [note, setNote] = useState('');
  const [deployment, setDeployment] = useState('');
  const qc = useQueryClient();
  const action = actions.includes(choice) ? choice : actions[0];
  const mutation = useMutation({
    mutationFn: async (selected: Action) => {
      const params = { path: { id: issue.id } };
      const version = issue.version;
      if (version === undefined) throw new Error('Request version is unavailable. Reload this request.');
      switch (selected) {
        case 'accept': {
          const { data, error, response } = await api.POST('/api/issues/{id}/accept/', { params, body: { version, tentative_delivery_date: later ? null : date || null, tentative_delivery_later: later, comment } });
          return requireIssue(data, error, response.status);
        }
        case 'reject': {
          const { data, error, response } = await api.POST('/api/issues/{id}/reject/', { params, body: { version, reason, comment } });
          return requireIssue(data, error, response.status);
        }
        case 'revise-date': {
          const { data, error, response } = await api.POST('/api/issues/{id}/revise-date/', { params, body: { version, tentative_delivery_date: later ? null : date || null, tentative_delivery_later: later, comment } });
          return requireIssue(data, error, response.status);
        }
        case 'assign': {
          const { data, error, response } = await api.POST('/api/issues/{id}/assign/', { params, body: { version, assignee: Number(assignee), comment } });
          return requireIssue(data, error, response.status);
        }
        case 'start': {
          const { data, error, response } = await api.POST('/api/issues/{id}/start/', { params, body: { version, comment } });
          return requireIssue(data, error, response.status);
        }
        case 'deliver': {
          const { data, error, response } = await api.POST('/api/issues/{id}/deliver/', { params, body: { version, delivery_note: note, deployment_details: deployment, comment } });
          return requireIssue(data, error, response.status);
        }
        case 'verify': {
          const { data, error, response } = await api.POST('/api/issues/{id}/verify/', { params, body: { version, comment } });
          return requireIssue(data, error, response.status);
        }
        case 'fail-verification': {
          const { data, error, response } = await api.POST('/api/issues/{id}/fail-verification/', { params, body: { version, reason, comment } });
          return requireIssue(data, error, response.status);
        }
        case 'close': {
          const { data, error, response } = await api.POST('/api/issues/{id}/close/', { params, body: { version, comment } });
          return requireIssue(data, error, response.status);
        }
        case 'reopen': {
          const { data, error, response } = await api.POST('/api/issues/{id}/reopen/', { params, body: { version, reason, comment } });
          return requireIssue(data, error, response.status);
        }
      }
    },
    onSuccess: () => {
      setReason(''); setNote(''); setDeployment(''); setComment('');
      qc.invalidateQueries({ queryKey: ['issues'] });
      qc.invalidateQueries({ queryKey: ['report'] });
    },
  });
  if (!action) return <p className="muted">No action is needed from you right now.</p>;
  const dateAction = action === 'accept' || action === 'revise-date';
  const reasonAction = action === 'reject' || action === 'fail-verification' || action === 'reopen';
  return (
    <form
      className="stack"
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        mutation.mutate(action);
      }}
    >
      {actions.length > 1 && (
        <div className="action-choices" role="group" aria-label="Choose an action">
          {actions.map(item => (
            <button
              type="button"
              key={item}
              className={item === action ? 'btn small primary' : 'btn small'}
              aria-pressed={item === action}
              onClick={() => setChoice(item)}
            >
              {LABEL[item]}
            </button>
          ))}
        </div>
      )}
      {dateAction && (
        <>
          <label>
            Tentative delivery date
            <input type="date" value={date} disabled={later} onChange={event => setDate(event.target.value)} required={!later} />
          </label>
          <label className="check">
            <input type="checkbox" checked={later} onChange={event => setLater(event.target.checked)} /> To be provided later
          </label>
        </>
      )}
      {reasonAction && (
        <label>
          Reason
          <textarea rows={3} value={reason} onChange={event => setReason(event.target.value)} required />
        </label>
      )}
      {action === 'assign' && (
        <label>
          Responsible DataSoft user
          <select value={assignee} onChange={event => setAssignee(event.target.value)} required>
            <option value="">Select user</option>
            {assignees.data?.map(user => (
              <option key={user.id} value={user.id}>
                {user.full_name}
              </option>
            ))}
          </select>
        </label>
      )}
      {action === 'deliver' && (
        <>
          <label>
            What changed
            <textarea rows={3} value={note} onChange={event => setNote(event.target.value)} required />
          </label>
          <label>
            Version or deployment details
            <textarea rows={2} value={deployment} onChange={event => setDeployment(event.target.value)} required />
          </label>
        </>
      )}
      {action === 'verify' && (
        <aside className="alert info verification-context">
          <strong>Agreed acceptance criteria</strong>
          <p className="prewrap">{issue.acceptance_criteria || 'No acceptance criteria were provided.'}</p>
          <strong>Delivery note</strong>
          <p className="prewrap">{issue.delivery_note || 'No delivery note is available.'}</p>
        </aside>
      )}
      <label>
        Comment (optional)
        <textarea rows={2} value={comment} onChange={event => setComment(event.target.value)} maxLength={5000} />
      </label>
      {assignees.isError && action === 'assign' && <p className="alert error">{assignees.error.message}</p>}
      {mutation.isError && (
        <p className="alert error" role="alert">
          {mutation.error.message}
        </p>
      )}
      <button className="btn primary" disabled={mutation.isPending}>
        {mutation.isPending ? 'Saving…' : LABEL[action]}
      </button>
    </form>
  );
}


export function WorkflowSettingsPanel() {
  const qc = useQueryClient();
  const settings = useQuery({
    queryKey: ['workflow', 'settings'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/issues/workflow-settings/');
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
  const [edited, setEdited] = useState<number | null>(null);
  const save = useMutation({
    mutationFn: async (days: number) => {
      const { data, error } = await api.PATCH('/api/issues/workflow-settings/', { body: { reopen_days: days } });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['workflow', 'settings'] }),
  });
  if (settings.isPending) return null;
  return <form className="card toolbar" onSubmit={(event: FormEvent) => { event.preventDefault(); save.mutate(edited ?? settings.data?.reopen_days ?? 30); }}>
    <label>Reopen window (days)<input type="number" min={1} max={365} value={edited ?? settings.data?.reopen_days ?? 30} onChange={event => setEdited(Number(event.target.value))} /></label>
    <button className="btn" disabled={save.isPending}>Save policy</button>
    {settings.isError && <p className="alert error">{settings.error.message}</p>}
    {save.isError && <p className="alert error">{save.error.message}</p>}
  </form>;
}
