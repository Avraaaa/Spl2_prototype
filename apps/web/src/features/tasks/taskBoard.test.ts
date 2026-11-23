import { describe, expect, it } from 'vitest';
import type { components } from '../../api/generated/schema';
import { filterTasks, groupTasks, moveTask, rollbackTaskMove } from './taskBoard.helpers';

type Task = components['schemas']['Task'];
const task = (id: number, status: Task['status'], title = `Task ${id}`, assignee: number | null = null): Task => ({
  id, issue: id, issue_reference: `SR-${id}`, title, assignee, assignee_name: assignee ? 'Alex Example' : null,
  status, commit_url: '', pull_request_url: '', created_at: '', updated_at: '',
});

describe('task board helpers', () => {
  it('groups every status in board order, including empty columns', () => {
    expect(groupTasks([task(1, 'done'), task(2, 'todo')])).toEqual({
      todo: [task(2, 'todo')], in_progress: [], done: [task(1, 'done')],
    });
  });
  it('filters by owner, assignee, title and request reference', () => {
    const tasks = [task(1, 'todo', 'Review login', 4), task(2, 'done', 'Update ledger', 8)];
    expect(filterTasks(tasks, { mineId: 4, mineOnly: true, assignee: '', search: '' })).toEqual([tasks[0]]);
    expect(filterTasks(tasks, { mineId: 4, mineOnly: false, assignee: '8', search: 'sr-2' })).toEqual([tasks[1]]);
    expect(filterTasks(tasks, { mineId: 4, mineOnly: false, assignee: '', search: 'LOGIN' })).toEqual([tasks[0]]);
  });
  it('moves a task optimistically and restores the previous list on failure', () => {
    const tasks = [task(1, 'todo'), task(2, 'done')];
    const optimistic = moveTask(tasks, 1, 'in_progress');
    expect(optimistic[0]?.status).toBe('in_progress');
    expect(rollbackTaskMove(optimistic, tasks)).toEqual(tasks);
  });
});
