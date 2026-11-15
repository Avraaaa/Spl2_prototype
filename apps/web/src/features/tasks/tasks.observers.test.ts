import { describe, expect, it } from 'vitest';
import type { components } from '../../api/generated/schema';
import { editBodyFor, editDraftFor } from './TasksPage';

type Task = components['schemas']['Task'];

const task = {
  id: 7,
  issue: 4,
  issue_reference: 'SR-1007',
  title: 'Synthetic task',
  assignee: 12,
  assignee_name: 'Demo Support',
  status: 'todo',
  commit_url: 'https://git.example/commit/old',
  pull_request_url: '',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
} satisfies Task;

describe('task editing', () => {
  it('loads editable assignment and Git references from a task', () => {
    expect(editDraftFor(task)).toEqual({
      assignee: '12',
      commit_url: 'https://git.example/commit/old',
      pull_request_url: '',
    });
  });

  it('sends null when a task is deliberately unassigned', () => {
    expect(editBodyFor({ assignee: '', commit_url: '', pull_request_url: '' })).toEqual({
      assignee: null,
      commit_url: '',
      pull_request_url: '',
    });
  });
});
