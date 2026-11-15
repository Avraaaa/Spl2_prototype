import { useState, type FormEvent, type ReactNode } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import type { components } from '../../api/generated/schema';
import { errorMessage } from '../auth/hooks';
import { hasRole, type PortalUser } from '../auth/roles';
import { ErrorState, LoadingState } from '../ui/EmptyState';
import { Dropzone } from '../ui/Dropzone';
import { PageHeader } from '../ui/PageHeader';
import { PRIORITY_CODES, priorityLabel, TYPE_CODES, typeLabel } from '../ui/labels';
import {
  blankDraft,
  draftFromIssue,
  FieldError,
  hasErrors,
  parseServerErrors,
  requiredFields,
  validateDraft,
  type Draft,
  type DraftErrors,
} from './draftForm';
import { ISSUE_KEY, useIssue, useIssues, useProducts } from './hooks';
import {
  ATTACHMENT_ACCEPT,
  attachmentKind,
  formatFileSize,
  uploadAttachment,
  validateAttachment,
} from './attachments';

type Issue = components['schemas']['Issue'];
type Product = components['schemas']['Product'];
type Stored = { id: number; version: number };
type QueuedFile = {
  key: string;
  file: File;
  status: 'ready' | 'uploading' | 'uploaded' | 'error';
  validationError?: string;
  error?: string;
};

function serverError(error: unknown): FieldError {
  const { fields, general } = parseServerErrors(error);
  const message = general || (hasErrors(fields) ? 'Please fix the highlighted fields.' : errorMessage(error));
  return new FieldError(message, fields);
}

type FieldProps = {
  name: keyof Draft;
  label: string;
  required: boolean;
  error?: string;
  children: ReactNode;
};

function Field({ name, label, required, error, children }: FieldProps) {
  return (
    <div className={error ? 'field has-error' : 'field'}>
      <label htmlFor={`draft-${name}`}>
        {label}
        {required && (
          <span className="req" aria-hidden="true">
            {' *'}
          </span>
        )}
        {required && <span className="sr-only"> (required)</span>}
      </label>
      {children}
      {error && (
        <span className="field-error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

/** Loads the stored draft (when editing) and mounts the form once, so its state starts from it. */
export function IssueDraftPage({ me }: { me: PortalUser }) {
  const params = useParams();
  const editing = params.id !== undefined;
  const id = editing ? Number(params.id) : 0;
  const issue = useIssue(id);
  if (!hasRole(me, 'ISSUE_OFFICER')) return <p className="alert error">Issue Officer role required.</p>;
  if (editing && issue.isPending) return <LoadingState label="Loading draft…" />;
  if (editing && (issue.isError || issue.data?.status !== 'DRAFT' || issue.data.created_by !== me.id)) {
    return <p className="alert error">Draft unavailable.</p>;
  }
  return <DraftForm key={id} existing={editing ? issue.data : undefined} />;
}

function DraftForm({ existing }: { existing?: Issue }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const products = useProducts();
  const related = useIssues({ status: 'SUBMITTED' });
  const [draft, setDraft] = useState<Draft>(() => (existing ? draftFromIssue(existing) : blankDraft()));
  const [stored, setStored] = useState<Stored | null>(existing ? { id: existing.id, version: existing.version ?? 1 } : null);
  const [errors, setErrors] = useState<DraftErrors>({});
  const [attachments, setAttachments] = useState<QueuedFile[]>([]);

  const addAttachments = (files: File[]) => {
    setAttachments(current => [
      ...current,
      ...files.map((file, index) => {
        const validationError = validateAttachment(file) ?? undefined;
        return {
          key: `${file.name}-${file.size}-${file.lastModified}-${Date.now()}-${index}`,
          file,
          status: validationError ? ('error' as const) : ('ready' as const),
          validationError,
          error: validationError,
        };
      }),
    ]);
  };

  const updateAttachment = (key: string, change: Partial<QueuedFile>) => {
    setAttachments(current => current.map(item => (item.key === key ? { ...item, ...change } : item)));
  };

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => {
    setDraft(current => ({ ...current, [key]: value }));
    setErrors(current => {
      if (!(key in current)) return current;
      const next = { ...current };
      delete next[key];
      return next;
    });
  };

  const persist = async (): Promise<Stored> => {
    if (stored) {
      const { data, error, response } = await api.PATCH('/api/issues/{id}/', {
        params: { path: { id: stored.id } },
        body: { ...draft, version: stored.version },
      });
      if (response.status === 409) throw new Error('This request was changed by someone else — reload.');
      if (!data) throw serverError(error);
      return { id: data.id, version: data.version ?? 1 };
    }
    const { data, error } = await api.POST('/api/issues/', { body: draft });
    if (!data) throw serverError(error);
    return { id: data.id, version: data.version ?? 1 };
  };

  const save = useMutation({
    mutationFn: async (submit: boolean) => {
      const saved = await persist();
      setStored(saved);
      let uploadFailed = false;
      for (const item of attachments) {
        if (item.validationError || item.status === 'uploaded') {
          if (item.validationError) uploadFailed = true;
          continue;
        }
        updateAttachment(item.key, { status: 'uploading', error: undefined });
        try {
          await uploadAttachment(saved.id, item.file);
          updateAttachment(item.key, { status: 'uploaded' });
        } catch (error) {
          uploadFailed = true;
          updateAttachment(item.key, {
            status: 'error',
            error: error instanceof Error ? error.message : 'Upload failed.',
          });
        }
      }
      if (uploadFailed) {
        throw new Error('Your draft was saved, but one or more attachments could not be uploaded.');
      }
      if (!submit) return saved.id;
      const { data, error } = await api.POST('/api/issues/{id}/submit/', { params: { path: { id: saved.id } } });
      if (!data) {
        const failure = serverError(error);
        failure.message = `Your draft was saved but not submitted. ${failure.message}`;
        throw failure;
      }
      return data.id;
    },
    onSuccess: id => {
      qc.invalidateQueries({ queryKey: ISSUE_KEY });
      qc.invalidateQueries({ queryKey: ['report'] });
      navigate(`/issues/${id}`);
    },
    onError: error => {
      if (error instanceof FieldError) setErrors(error.fields);
    },
  });

  const run = (event: FormEvent | null, mode: 'save' | 'submit') => {
    event?.preventDefault();
    const found = validateDraft(draft, mode);
    setErrors(found);
    if (hasErrors(found)) return;
    save.mutate(mode === 'submit');
  };

  const required = new Set<keyof Draft>(requiredFields(draft.request_type));
  const selected = (products.data ?? []).find((p: Product) => p.id === draft.product);
  const field = (name: keyof Draft, label: string) => ({
    name,
    label,
    required: required.has(name),
    error: errors[name],
  });
  const text = (name: 'environment' | 'steps_to_reproduce' | 'expected_result' | 'actual_result' | 'description', rows: number) => (
    <textarea
      id={`draft-${name}`}
      rows={rows}
      value={draft[name] ?? ''}
      onChange={e => set(name, e.target.value)}
    />
  );

  return (
    <section className="stack">
      <PageHeader
        title={existing ? `Edit ${existing.reference}` : 'New request'}
        subtitle="Fields marked * are required before you can submit."
      />
      <form className="card form-grid" onSubmit={e => run(e, 'submit')} noValidate>
        <Field {...field('title', 'Title')}>
          <input
            id="draft-title"
            maxLength={200}
            value={draft.title ?? ''}
            onChange={e => set('title', e.target.value)}
          />
        </Field>
        <Field {...field('description', 'Description')}>{text('description', 4)}</Field>
        <div className="form-row">
          <Field {...field('request_type', 'Type')}>
            <select
              id="draft-request_type"
              value={draft.request_type ?? ''}
              onChange={e => set('request_type', e.target.value as Draft['request_type'])}
            >
              {TYPE_CODES.map(x => (
                <option key={x} value={x}>
                  {typeLabel(x)}
                </option>
              ))}
            </select>
          </Field>
          <Field {...field('priority', 'Priority')}>
            <select
              id="draft-priority"
              value={draft.priority ?? ''}
              onChange={e => set('priority', e.target.value as Draft['priority'])}
            >
              {PRIORITY_CODES.map(x => (
                <option key={x} value={x}>
                  {priorityLabel(x)}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <div className="form-row">
          <Field {...field('product', 'Product')}>
            <select
              id="draft-product"
              value={draft.product ?? ''}
              onChange={e => {
                set('product', e.target.value ? Number(e.target.value) : null);
                set('module', null);
              }}
            >
              <option value="">Select product</option>
              {(products.data ?? []).map((p: Product) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </Field>
          <Field {...field('module', 'Module')}>
            <select
              id="draft-module"
              value={draft.module ?? ''}
              onChange={e => set('module', e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">No module</option>
              {selected?.modules
                .filter(m => m.is_active)
                .map(m => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
            </select>
          </Field>
        </div>
        <Field {...field('related_request', 'Related request')}>
          <select
            id="draft-related_request"
            value={draft.related_request ?? ''}
            onChange={e => set('related_request', e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">None</option>
            {(related.data ?? [])
              .filter(r => r.id !== stored?.id)
              .map(r => (
                <option key={r.id} value={r.id}>
                  {r.reference} — {r.title}
                </option>
              ))}
          </select>
        </Field>
        {draft.request_type === 'BUG' && (
          <fieldset className="bug-evidence">
            <legend>Bug evidence</legend>
            <Field {...field('environment', 'Environment')}>{text('environment', 2)}</Field>
            <Field {...field('steps_to_reproduce', 'Steps to reproduce')}>{text('steps_to_reproduce', 3)}</Field>
            <Field {...field('expected_result', 'Expected result')}>{text('expected_result', 2)}</Field>
            <Field {...field('actual_result', 'Actual result')}>{text('actual_result', 2)}</Field>
          </fieldset>
        )}
        <fieldset className="attachment-section">
          <legend>Attachments</legend>
          <Dropzone
            accept={ATTACHMENT_ACCEPT}
            disabled={save.isPending}
            onFiles={addAttachments}
            helper="PNG, JPG, GIF, PDF, TXT, LOG, CSV, ZIP, DOCX, XLSX or PPTX. Maximum 10 MB per file."
          />
          {attachments.length > 0 && (
            <ul className="upload-queue" aria-label="Files selected for upload">
              {attachments.map(item => (
                <li key={item.key} className={item.status === 'error' ? 'has-error' : ''}>
                  <span className={`file-icon kind-${attachmentKind(item.file.name)}`} aria-hidden="true" />
                  <span className="file-summary">
                    <strong>{item.file.name}</strong>
                    <span className="muted">
                      {formatFileSize(item.file.size)} · {item.status}
                    </span>
                    {item.error && <span className="field-error">{item.error}</span>}
                  </span>
                  <button
                    type="button"
                    className="btn small ghost"
                    disabled={save.isPending}
                    onClick={() => setAttachments(current => current.filter(file => file.key !== item.key))}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </fieldset>
        {products.isError && <ErrorState error={products.error} />}
        {save.isError && <ErrorState error={save.error} />}
        {hasErrors(errors) && !save.isError && (
          <p className="alert error" role="alert">
            Please fix the highlighted fields.
          </p>
        )}
        <div className="actions">
          <button type="button" className="btn" disabled={save.isPending} onClick={() => run(null, 'save')}>
            {save.isPending ? 'Saving…' : 'Save draft'}
          </button>
          <button type="submit" className="btn primary" disabled={save.isPending}>
            Submit request
          </button>
        </div>
      </form>
    </section>
  );
}
