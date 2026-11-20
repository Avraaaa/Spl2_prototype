import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import { errorMessage } from '../auth/hooks';
import { PageHeader } from '../ui/PageHeader';

const KEY = ['admin-labels'];

export function LabelAdminPage() {
  const qc = useQueryClient();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [keywords, setKeywords] = useState('');
  const labels = useQuery({
    queryKey: KEY,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/search/labels/');
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
  const create = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST('/api/search/labels/', {
        body: { name, description, keywords: keywords.split(',').map(item => item.trim()).filter(Boolean) },
      });
      if (!data) throw new Error(errorMessage(error));
    },
    onSuccess: () => { setName(''); setDescription(''); setKeywords(''); qc.invalidateQueries({ queryKey: KEY }); },
  });
  const update = useMutation({
    mutationFn: async ({ id, is_active }: { id: number; is_active: boolean }) => {
      const { data, error } = await api.PATCH('/api/search/labels/{id}/', { params: { path: { id } }, body: { is_active } });
      if (!data) throw new Error(errorMessage(error));
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });

  return (
    <section className="stack">
      <PageHeader title="Issue labels" subtitle="Define the labels and confidence rules used by suggestions." />
      <form className="card form-grid" onSubmit={(event: FormEvent) => { event.preventDefault(); create.mutate(); }}>
        <label>Name<input value={name} onChange={event => setName(event.target.value)} required maxLength={80} /></label>
        <label>Description<input value={description} onChange={event => setDescription(event.target.value)} maxLength={300} /></label>
        <label>Keywords<input value={keywords} onChange={event => setKeywords(event.target.value)} placeholder="login, sign in, authentication" /></label>
        {create.isError && <p className="alert error">{create.error.message}</p>}
        <button className="btn primary" disabled={create.isPending}>Add label</button>
      </form>
      <div className="card table-wrap">
        <table><thead><tr><th>Label</th><th>Description</th><th>Threshold</th><th>Status</th><th /></tr></thead>
          <tbody>{(labels.data ?? []).map(label => (
            <tr key={label.id}>
              <td><strong>{label.name}</strong><div className="muted small">{label.keywords.join(', ')}</div></td>
              <td>{label.description || '—'}</td>
              <td>{label.confidence_threshold}</td>
              <td>{label.is_active ? 'Active' : 'Inactive'}</td>
              <td><button className="btn small" onClick={() => update.mutate({ id: label.id, is_active: !label.is_active })}>{label.is_active ? 'Deactivate' : 'Activate'}</button></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  );
}
