import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { components } from '../../api/generated/schema';
import { errorMessage } from '../auth/hooks';
import type { PortalUser } from '../auth/roles';

type Task = components['schemas']['Task'];
type TaskWrite = components['schemas']['TaskWriteRequest'];
type TaskEdit = components['schemas']['PatchedTaskEditRequest'];
const statuses = ['todo', 'in_progress', 'done'] as const;

type EditDraft = {
  assignee: string;
  commit_url: string;
  pull_request_url: string;
};

export function editDraftFor(task: Task): EditDraft {
  return {
    assignee: task.assignee?.toString() ?? '',
    commit_url: task.commit_url ?? '',
    pull_request_url: task.pull_request_url ?? '',
  };
}

export function editBodyFor(draft: EditDraft): TaskEdit {
  return {
    assignee: draft.assignee ? Number(draft.assignee) : null,
    commit_url: draft.commit_url,
    pull_request_url: draft.pull_request_url,
  };
}

export function TasksPage({ me }: { me: PortalUser }) {
  const qc = useQueryClient();
  const key = ['tasks', me.id] as const;
  const [board, setBoard] = useState(false);
  const [draft, setDraft] = useState({ issue: '', title: '', assignee: '', commit_url: '', pull_request_url: '' });
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<EditDraft>({ assignee: '', commit_url: '', pull_request_url: '' });
  const tasks = useQuery({ queryKey: key, queryFn: async () => {
    const { data, error } = await api.GET('/api/tasks/');
    if (!data) throw new Error(errorMessage(error));
    return data;
  } });
  const issues = useQuery({ queryKey: ['issues', me.id, 'task-picker'], queryFn: async () => {
    const { data, error } = await api.GET('/api/issues/');
    if (!data) throw new Error(errorMessage(error));
    return data;
  } });
  const assignees = useQuery({ queryKey: ['assignees', me.id], queryFn: async () => {
    const { data, error } = await api.GET('/api/issues/assignees/');
    if (!data) throw new Error(errorMessage(error));
    return data;
  } });
  const create = useMutation({ mutationFn: async () => {
    const body: TaskWrite = { issue: Number(draft.issue), title: draft.title, assignee: draft.assignee ? Number(draft.assignee) : null, commit_url: draft.commit_url, pull_request_url: draft.pull_request_url };
    const { data, error } = await api.POST('/api/tasks/', { body });
    if (!data) throw new Error(errorMessage(error));
  }, onSuccess: () => { setDraft({ issue: '', title: '', assignee: '', commit_url: '', pull_request_url: '' }); qc.invalidateQueries({ queryKey: key }); } });
  const move = useMutation({ mutationFn: async ({ id, status }: { id: number; status: Task['status'] }) => {
    const { data, error } = await api.PATCH('/api/tasks/{id}/', { params: { path: { id } }, body: { status } });
    if (!data) throw new Error(errorMessage(error));
  }, onSuccess: () => qc.invalidateQueries({ queryKey: key }) });
  const update = useMutation({ mutationFn: async ({ id, body }: { id: number; body: TaskEdit }) => {
    const { data, error } = await api.PATCH('/api/tasks/{id}/', { params: { path: { id } }, body });
    if (!data) throw new Error(errorMessage(error));
  }, onSuccess: () => {
    setEditingId(null);
    qc.invalidateQueries({ queryKey: key });
  } });
  const beginEdit = (task: Task) => {
    setEditingId(task.id);
    setEditDraft(editDraftFor(task));
  };
  const renderTask = (task: Task) => <div className="card" key={task.id}>
    <strong>{task.title}</strong> · <Link to={`/issues/${task.issue}`}>{task.issue_reference}</Link>
    <p className="muted">{task.assignee_name ?? 'Unassigned'} · {task.status.replaceAll('_', ' ')}</p>
    {task.commit_url && <p><a href={task.commit_url} target="_blank" rel="noreferrer">Commit</a></p>}
    {task.pull_request_url && <p><a href={task.pull_request_url} target="_blank" rel="noreferrer">Pull request</a></p>}
    {editingId === task.id ? <form className="task-edit" onSubmit={event => { event.preventDefault(); update.mutate({ id: task.id, body: editBodyFor(editDraft) }); }}>
      <label>Assignee<select value={editDraft.assignee} onChange={event => setEditDraft({ ...editDraft, assignee: event.target.value })}><option value="">Unassigned</option>{(assignees.data ?? []).map(user => <option value={user.id} key={user.id}>{user.full_name}</option>)}</select></label>
      <label>Commit URL<input type="url" value={editDraft.commit_url} onChange={event => setEditDraft({ ...editDraft, commit_url: event.target.value })} /></label>
      <label>Pull request URL<input type="url" value={editDraft.pull_request_url} onChange={event => setEditDraft({ ...editDraft, pull_request_url: event.target.value })} /></label>
      <div className="actions"><button className="btn small primary" disabled={update.isPending}>Save task</button><button type="button" className="btn small ghost" onClick={() => setEditingId(null)}>Cancel</button></div>
    </form> : null}
    <div className="actions"><button className="btn small" onClick={() => beginEdit(task)}>Edit details</button>{statuses.filter(s => s !== task.status).map(s => <button className="btn small" key={s} disabled={move.isPending} onClick={() => move.mutate({ id: task.id, status: s })}>Move to {s.replaceAll('_', ' ')}</button>)}</div>
    <TaskNotes id={task.id} userId={me.id} />
  </div>;
  return <section className="stack"><div className="page-head"><h1>Internal tasks</h1><button className="btn" onClick={() => setBoard(!board)}>{board ? 'List view' : 'Kanban board'}</button></div>
    <form className="card form-grid" onSubmit={e => { e.preventDefault(); create.mutate(); }}>
      <h3>New task</h3><label>Request<select required value={draft.issue} onChange={e => setDraft({ ...draft, issue: e.target.value })}><option value="">Choose request</option>{(issues.data ?? []).map(issue => <option key={issue.id} value={issue.id}>{issue.reference} · {issue.title}</option>)}</select></label>
      <label>Title<input required maxLength={200} value={draft.title} onChange={e => setDraft({ ...draft, title: e.target.value })} /></label>
      <label>Assignee<select value={draft.assignee} onChange={e => setDraft({ ...draft, assignee: e.target.value })}><option value="">Unassigned</option>{(assignees.data ?? []).map(user => <option value={user.id} key={user.id}>{user.full_name}</option>)}</select></label>
      <label>Commit URL<input type="url" value={draft.commit_url} onChange={e => setDraft({ ...draft, commit_url: e.target.value })} /></label>
      <label>Pull request URL<input type="url" value={draft.pull_request_url} onChange={e => setDraft({ ...draft, pull_request_url: e.target.value })} /></label>
      <button className="btn primary" disabled={create.isPending}>Create task</button>
    </form>
    {(tasks.isError || issues.isError || create.isError || move.isError || update.isError) && <p className="alert error">{tasks.error?.message ?? issues.error?.message ?? create.error?.message ?? move.error?.message ?? update.error?.message}</p>}
    {board ? <div className="grid">{statuses.map(status => <div key={status} className="stack"><h2>{status.replaceAll('_', ' ')}</h2>{(tasks.data ?? []).filter(t => t.status === status).map(renderTask)}</div>)}</div> : <div className="stack">{(tasks.data ?? []).map(renderTask)}</div>}
  </section>;
}

function TaskNotes({ id, userId }: { id: number; userId: number }) {
  const qc = useQueryClient();
  const [body, setBody] = useState('');
  const notes = useQuery({ queryKey: ['task-notes', userId, id], queryFn: async () => {
    const { data, error } = await api.GET('/api/tasks/{id}/notes/', { params: { path: { id } } });
    if (!data) throw new Error(errorMessage(error));
    return data;
  } });
  const add = useMutation({ mutationFn: async () => {
    const { data, error } = await api.POST('/api/tasks/{id}/notes/', { params: { path: { id } }, body: { body } });
    if (!data) throw new Error(errorMessage(error));
  }, onSuccess: () => { setBody(''); qc.invalidateQueries({ queryKey: ['task-notes', userId, id] }); } });
  return <div><h4>Internal notes</h4>{(notes.data ?? []).map(note => <p key={note.id}>{note.author_name}: {note.body}</p>)}
    <form onSubmit={e => { e.preventDefault(); add.mutate(); }}><input aria-label="Task note" required value={body} onChange={e => setBody(e.target.value)} /><button className="btn small" disabled={add.isPending}>Save note</button></form>
    {(notes.error || add.error) && <p className="alert error">{notes.error?.message ?? add.error?.message}</p>}
  </div>;
}
