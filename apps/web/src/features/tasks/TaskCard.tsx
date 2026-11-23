import { useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import type { Task, TaskStatus } from './taskBoard.helpers';

const statuses: TaskStatus[] = ['todo', 'in_progress', 'done'];
const labels: Record<TaskStatus, string> = { todo: 'To do', in_progress: 'In progress', done: 'Done' };

export function TaskCard({ task, onMove, onEdit, notes, editor, dragging = false }: {
  task: Task; onMove: (id: number, status: TaskStatus) => void; onEdit: () => void; notes: ReactNode; editor?: ReactNode; dragging?: boolean;
}) {
  const [details, setDetails] = useState(false);
  const [showNotes, setShowNotes] = useState(false);
  const initials = task.assignee_name?.split(/\s+/).map(part => part[0]).slice(0, 2).join('').toUpperCase();
  return <article className={`task-card${dragging ? ' is-dragging' : ''}`}>
    <strong>{task.title}</strong>
    <Link className="task-reference" to={`/issues/${task.issue}`}>{task.issue_reference}</Link>
    <span className="task-assignee">{initials && <span className="task-avatar" aria-hidden="true">{initials}</span>}{task.assignee_name ?? 'Unassigned'}</span>
    <div className="task-links">{task.commit_url && <a href={task.commit_url} target="_blank" rel="noreferrer" aria-label="Commit link" title="Commit">⌘</a>}{task.pull_request_url && <a href={task.pull_request_url} target="_blank" rel="noreferrer" aria-label="Pull request link" title="Pull request">⑂</a>}</div>
    <div className="task-card-actions"><button className="btn small" onClick={onEdit}>Edit details</button><button className="btn small" onClick={() => setShowNotes(!showNotes)} aria-expanded={showNotes}>Notes</button><button className="btn small" onClick={() => setDetails(!details)} aria-expanded={details}>Move</button></div>
    {details && <div className="task-move-actions" aria-label={`Move ${task.title}`}>{statuses.filter(status => status !== task.status).map(status => <button className="btn small" key={status} onClick={() => onMove(task.id, status)}>Move to {labels[status]}</button>)}</div>}
    {editor}
    {showNotes && <div className="task-notes-panel">{notes}</div>}
  </article>;
}
