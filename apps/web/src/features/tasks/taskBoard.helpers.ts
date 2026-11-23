import type { components } from '../../api/generated/schema';

export type Task = components['schemas']['Task'];
export type TaskStatus = Task['status'];
export const taskStatuses: TaskStatus[] = ['todo', 'in_progress', 'done'];
export type TaskFilters = { mineId: number; mineOnly: boolean; assignee: string; search: string };
export type TaskGroups = Record<TaskStatus, Task[]>;

export function groupTasks(tasks: Task[]): TaskGroups {
  return { todo: tasks.filter(task => task.status === 'todo'), in_progress: tasks.filter(task => task.status === 'in_progress'), done: tasks.filter(task => task.status === 'done') };
}

export function filterTasks(tasks: Task[], filters: TaskFilters): Task[] {
  const needle = filters.search.trim().toLocaleLowerCase();
  return tasks.filter(task => (!filters.mineOnly || task.assignee === filters.mineId)
    && (!filters.assignee || task.assignee?.toString() === filters.assignee)
    && (!needle || `${task.title} ${task.issue_reference}`.toLocaleLowerCase().includes(needle)));
}

export function moveTask(tasks: Task[], id: number, status: TaskStatus): Task[] {
  return tasks.map(task => task.id === id ? { ...task, status } : task);
}

export function rollbackTaskMove(_current: Task[], previous: Task[]): Task[] {
  return previous;
}

export function readBoardPreference(): boolean {
  try { return window.localStorage.getItem('tasks-board-view') !== 'list'; } catch { return true; }
}

export function saveBoardPreference(board: boolean): void {
  try { window.localStorage.setItem('tasks-board-view', board ? 'board' : 'list'); } catch { /* Storage may be disabled. */ }
}
