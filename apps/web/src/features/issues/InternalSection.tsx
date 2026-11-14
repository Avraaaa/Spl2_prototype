import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import { errorMessage } from '../auth/hooks';
import type { PortalUser } from '../auth/roles';
import { EmptyState, ErrorState } from '../ui/EmptyState';
import { StatusBadge } from '../ui/StatusBadge';

/** DataSoft-only notes and linked tasks. Never rendered for bank users. */
export function InternalSection({ id, me }: { id: number; me: PortalUser }) {
  const qc = useQueryClient();
  const [note, setNote] = useState('');
  const [title, setTitle] = useState('');
  const notes = useQuery({
    queryKey: ['internal-notes', me.id, id],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/issues/{id}/internal-notes/', { params: { path: { id } } });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
  const tasks = useQuery({
    queryKey: ['tasks', me.id],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/tasks/');
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
  const addNote = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST('/api/issues/{id}/internal-notes/', {
        params: { path: { id } },
        body: { body: note },
      });
      if (!data) throw new Error(errorMessage(error));
    },
    onSuccess: () => {
      setNote('');
      qc.invalidateQueries({ queryKey: ['internal-notes', me.id, id] });
    },
  });
  const addTask = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST('/api/tasks/', { body: { issue: id, title } });
      if (!data) throw new Error(errorMessage(error));
    },
    onSuccess: () => {
      setTitle('');
      qc.invalidateQueries({ queryKey: ['tasks', me.id] });
    },
  });
  const linked = (tasks.data ?? []).filter(task => task.issue === id);
  return (
    <section className="card internal stack" aria-label="Internal">
      <div>
        <h3>Internal</h3>
        <p className="internal-flag">Internal — not visible to the bank</p>
      </div>
      <h4>Notes</h4>
      {notes.isError && <ErrorState error={notes.error} />}
      {notes.data?.length === 0 && <EmptyState>No internal notes.</EmptyState>}
      {(notes.data ?? []).map(item => (
        <p key={item.id}>
          <strong>{item.author_name}:</strong> {item.body}
        </p>
      ))}
      <form
        className="stack"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          addNote.mutate();
        }}
      >
        <label>
          New internal note
          <textarea required rows={2} value={note} onChange={e => setNote(e.target.value)} />
        </label>
        {addNote.isError && <ErrorState error={addNote.error} />}
        <div>
          <button className="btn" disabled={addNote.isPending}>
            Save note
          </button>
        </div>
      </form>
      <h4>Linked tasks</h4>
      {tasks.isError && <ErrorState error={tasks.error} />}
      {linked.length === 0 && <EmptyState>No linked tasks.</EmptyState>}
      {linked.map(task => (
        <p key={task.id}>
          {task.title} · <StatusBadge status={task.status.toUpperCase()} />
        </p>
      ))}
      <form
        className="stack"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          addTask.mutate();
        }}
      >
        <label>
          Task title
          <input required maxLength={200} value={title} onChange={e => setTitle(e.target.value)} />
        </label>
        {addTask.isError && <ErrorState error={addTask.error} />}
        <div className="actions">
          <button className="btn" disabled={addTask.isPending}>
            Create task
          </button>
          <Link to="/tasks">Open task board</Link>
        </div>
      </form>
    </section>
  );
}
