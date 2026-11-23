import { useState } from 'react';
import type { Task, TaskStatus } from './taskBoard.helpers';
import { filterTasks, groupTasks, taskStatuses } from './taskBoard.helpers';
import { TaskCard } from './TaskCard';
import type { ReactNode } from 'react';

const labels: Record<TaskStatus, string> = { todo: 'To do', in_progress: 'In progress', done: 'Done' };
export function TaskBoard({ tasks, userId, assignees, onMove, onEdit, notes, editor }: { tasks: Task[]; userId: number; assignees: { id: number; full_name: string }[]; onMove: (id: number, status: TaskStatus) => void; onEdit: (task: Task) => void; notes: (id: number) => ReactNode; editor: (task: Task) => ReactNode }) {
  const [mineOnly, setMineOnly] = useState(false);
  const [assignee, setAssignee] = useState('');
  const [search, setSearch] = useState('');
  const [draggedId, setDraggedId] = useState<number | null>(null);
  const visible = filterTasks(tasks, { mineId: userId, mineOnly, assignee, search });
  const groups = groupTasks(visible);
  return <section className="task-board-wrap" aria-label="Internal task board">
    <div className="task-filters"><label>Tasks<select value={mineOnly ? 'mine' : 'all'} onChange={event => setMineOnly(event.target.value === 'mine')}><option value="all">All tasks</option><option value="mine">My tasks</option></select></label><label>Assignee<select value={assignee} onChange={event => setAssignee(event.target.value)}><option value="">All assignees</option>{assignees.map(person => <option key={person.id} value={person.id}>{person.full_name}</option>)}</select></label><label>Search tasks<input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Title or request reference" /></label></div>
    <div className="task-board">{taskStatuses.map(status => <section className={`task-column${draggedId !== null ? ' can-drop' : ''}`} key={status} aria-label={`${labels[status]} tasks`} onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); const id = Number(event.dataTransfer.getData('text/plain')); if (id) onMove(id, status); setDraggedId(null); }}>
      <header><h2>{labels[status]}</h2><span className="task-count" aria-label={`${groups[status].length} tasks`}>{groups[status].length}</span></header>
      <div className="task-column-body">{groups[status].map(task => <div key={task.id} draggable onDragStart={event => { event.dataTransfer.setData('text/plain', String(task.id)); event.dataTransfer.effectAllowed = 'move'; setDraggedId(task.id); }} onDragEnd={() => setDraggedId(null)}><TaskCard task={task} onMove={onMove} onEdit={() => onEdit(task)} notes={notes(task.id)} editor={editor(task)} dragging={draggedId === task.id} /></div>)}{groups[status].length === 0 && <p className="task-column-empty">Drop a task here</p>}</div>
    </section>)}</div>
  </section>;
}
