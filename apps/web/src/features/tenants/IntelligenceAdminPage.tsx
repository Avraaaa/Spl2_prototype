import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import { errorMessage } from '../auth/hooks';
import { PageHeader } from '../ui/PageHeader';
import { evaluationMetric, type EvaluationMetric } from './evaluationMetrics';

const PATTERNS = ['admin', 'masking-patterns'] as const;
const TOPICS = ['admin', 'topics'] as const;

export function IntelligenceAdminPage() {
  const qc = useQueryClient();
  const [name, setName] = useState('');
  const [pattern, setPattern] = useState('');
  const [replacement, setReplacement] = useState('[SENSITIVE]');
  const [editingPattern, setEditingPattern] = useState<number | null>(null);
  const [auditResult, setAuditResult] = useState<string | null>(null);
  const patterns = useQuery({
    queryKey: PATTERNS,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/issues/masking-patterns/');
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
  const topics = useQuery({
    queryKey: TOPICS,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/search/topics/');
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
  const evaluation = useQuery({
    queryKey: ['admin', 'evaluation'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/search/evaluation/');
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
  const createPattern = useMutation({
    mutationFn: async () => {
      if (editingPattern !== null) {
        const { data, error } = await api.PATCH('/api/issues/masking-patterns/{id}/', {
          params: { path: { id: editingPattern } }, body: { name, pattern, replacement },
        });
        if (!data) throw new Error(errorMessage(error));
        return;
      }
      const { data, error } = await api.POST('/api/issues/masking-patterns/', {
        body: { name, pattern, replacement, is_active: true },
      });
      if (!data) throw new Error(errorMessage(error));
    },
    onSuccess: () => {
      setName('');
      setPattern('');
      setReplacement('[SENSITIVE]');
      setEditingPattern(null);
      qc.invalidateQueries({ queryKey: PATTERNS });
    },
  });
  const togglePattern = useMutation({
    mutationFn: async ({ id, is_active }: { id: number; is_active: boolean }) => {
      const { data, error } = await api.PATCH('/api/issues/masking-patterns/{id}/', {
        params: { path: { id } }, body: { is_active },
      });
      if (!data) throw new Error(errorMessage(error));
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: PATTERNS }),
  });
  const reviewTopic = useMutation({
    mutationFn: async ({ id, status }: { id: number; status: 'accepted' | 'rejected' }) => {
      const { data, error } = await api.PATCH('/api/search/topics/{id}/', {
        params: { path: { id } }, body: { status },
      });
      if (!data) throw new Error(errorMessage(error));
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: TOPICS }),
  });
  const addTopicLabel = useMutation({
    mutationFn: async (topic: NonNullable<typeof topics.data>[number]) => {
      const { data, error } = await api.POST('/api/search/labels/', {
        body: { name: topic.title.slice(0, 80), description: `Emerging topic: ${topic.title}`.slice(0, 300), keywords: topic.keywords.slice(0, 30) },
      });
      if (!data) throw new Error(errorMessage(error));
      const reviewed = await api.PATCH('/api/search/topics/{id}/', {
        params: { path: { id: topic.id } }, body: { status: 'accepted' },
      });
      if (!reviewed.data) throw new Error(errorMessage(reviewed.error));
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: TOPICS });
      qc.invalidateQueries({ queryKey: ['admin-labels'] });
    },
  });
  const verifyAudit = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.GET('/api/audit/verify/');
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
    onSuccess: result => setAuditResult(JSON.stringify(result, null, 2) ?? String(result)),
  });

  return (
    <section className="stack">
      <PageHeader title="Intelligence & privacy" subtitle="Review suggestions, privacy rules, and audit integrity." />
      <section className="card stack" aria-labelledby="masking-title">
        <h2 id="masking-title">Sensitive text patterns</h2>
        <p className="muted">Active custom rules run before text is saved. Built-in protections remain active.</p>
        <form className="form-row" onSubmit={(event: FormEvent) => { event.preventDefault(); createPattern.mutate(); }}>
          <label>Name<input value={name} onChange={event => setName(event.target.value)} maxLength={100} required /></label>
          <label>Regular expression<input value={pattern} onChange={event => setPattern(event.target.value)} maxLength={200} required /></label>
          <label>Replacement<input value={replacement} onChange={event => setReplacement(event.target.value)} maxLength={80} required /></label>
          <button className="btn primary" disabled={createPattern.isPending}>{editingPattern === null ? 'Add pattern' : 'Save pattern'}</button>
          {editingPattern !== null && <button className="btn" type="button" onClick={() => { setEditingPattern(null); setName(''); setPattern(''); setReplacement('[SENSITIVE]'); }}>Cancel edit</button>}
        </form>
        {patterns.isError && <p className="alert error" role="alert">{patterns.error.message}</p>}
        {createPattern.isError && <p className="alert error" role="alert">{createPattern.error.message}</p>}
        <div className="table-wrap"><table><thead><tr><th>Name</th><th>Pattern</th><th>Replacement</th><th>Status</th><th /></tr></thead>
          <tbody>{(patterns.data ?? []).map(item => <tr key={item.id}>
            <td>{item.name}</td><td><code>{item.pattern}</code></td><td>{item.replacement}</td>
            <td>{item.is_active ? 'Active' : 'Inactive'}</td>
            <td className="actions">
              <button className="btn small" type="button" onClick={() => { setEditingPattern(item.id); setName(item.name ?? ''); setPattern(item.pattern ?? ''); setReplacement(item.replacement ?? '[SENSITIVE]'); }}>Edit</button>
              <button className="btn small" type="button" onClick={() => togglePattern.mutate({ id: item.id, is_active: !item.is_active })}>{item.is_active ? 'Deactivate' : 'Activate'}</button>
            </td>
          </tr>)}</tbody>
        </table></div>
        {togglePattern.isError && <p className="alert error" role="alert">{togglePattern.error.message}</p>}
      </section>
      <section className="card stack" aria-labelledby="topics-title">
        <h2 id="topics-title">Emerging topics</h2>
        <p className="muted">Review grouped requests and add useful topics to the managed label list.</p>
        {topics.isError && <p className="alert error" role="alert">{topics.error.message}</p>}
        {(topics.data ?? []).length === 0 && <p className="muted">No topic proposals are available.</p>}
        {(topics.data ?? []).map(topic => <article className="topic-row" key={topic.id}>
          <div>
            <h3>{topic.title}</h3>
            <p className="muted">{topic.keywords.join(', ')} · {topic.issue_ids.length} requests · {topic.status}</p>
            <details>
              <summary>Review representative requests</summary>
              <pre className="audit-result">{JSON.stringify(topic.representatives, null, 2)}</pre>
            </details>
          </div>
          {topic.status === 'proposed' && <div className="actions">
            <button className="btn small primary" onClick={() => addTopicLabel.mutate(topic)} disabled={addTopicLabel.isPending}>Add as label</button>
            <button className="btn small" onClick={() => reviewTopic.mutate({ id: topic.id, status: 'accepted' })}>Accept</button>
            <button className="btn small" onClick={() => reviewTopic.mutate({ id: topic.id, status: 'rejected' })}>Reject</button>
          </div>}
        </article>)}
        {addTopicLabel.isError && <p className="alert error" role="alert">{addTopicLabel.error.message}</p>}
        {reviewTopic.isError && <p className="alert error" role="alert">{reviewTopic.error.message}</p>}
      </section>
      <div className="grid">
        <section className="card stack" aria-labelledby="audit-title">
          <h2 id="audit-title">Audit chain</h2>
          <p className="muted">Recompute every active bank’s audit chain and locate the first invalid record.</p>
          <button className="btn primary" onClick={() => verifyAudit.mutate()} disabled={verifyAudit.isPending}>{verifyAudit.isPending ? 'Verifying…' : 'Verify audit chains'}</button>
          {verifyAudit.isError && <p className="alert error" role="alert">{verifyAudit.error.message}</p>}
          {auditResult !== null && <pre className="audit-result" aria-live="polite">{auditResult}</pre>}
        </section>
        <section className="card stack" aria-labelledby="evaluation-title">
          <h2 id="evaluation-title">Suggestion accuracy</h2>
          {evaluation.isError && <p className="alert error" role="alert">{evaluation.error.message}</p>}
          {evaluation.data && <>
            <Metric title="Duplicate suggestions" data={evaluationMetric(evaluation.data.duplicate_feedback)} />
            <Metric title="Label suggestions" data={evaluationMetric(evaluation.data.label_feedback)} />
          </>}
        </section>
      </div>
    </section>
  );
}

function Metric({ title, data }: { title: string; data: EvaluationMetric }) {
  return <div className="metric-row"><strong>{title}</strong><span>{data.accepted} accepted of {data.total}</span><span>{Math.round(data.acceptance_rate * 100)}% acceptance</span></div>;
}
