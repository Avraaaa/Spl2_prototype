import type { Task, TaskStatus } from './taskBoard.helpers';
import { TaskCard } from './TaskCard';
import type { ReactNode } from 'react';

export function TaskList({ tasks, onMove, onEdit, notes, editor }: { tasks: Task[]; onMove: (id: number, status: TaskStatus) => void; onEdit: (task: Task) => void; notes: (id: number) => ReactNode; editor: (task: Task) => ReactNode }) {
  return <div className="task-list">{tasks.map(task => <TaskCard key={task.id} task={task} onMove={onMove} onEdit={() => onEdit(task)} notes={notes(task.id)} editor={editor(task)} />)}</div>;
}
