import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, readCookie } from '../../api/client';
import { errorMessage } from '../auth/hooks';
import type { PortalUser } from '../auth/roles';
import { EmptyState, ErrorState } from '../ui/EmptyState';
import { formatDateTime } from '../ui/format';

/** Comments visible to both sides (client and DataSoft). */
export function useComments(id: number, me: PortalUser) {
  return useQuery({
    queryKey: ['comments', me.id, id],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/issues/{id}/comments/', { params: { path: { id } } });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
}

export function CommentsPanel({ id, me }: { id: number; me: PortalUser }) {
  const qc = useQueryClient();
  const [body, setBody] = useState('');
  const comments = useComments(id, me);
  const add = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST('/api/issues/{id}/comments/', { params: { path: { id } }, body: { body } });
      if (!data) throw new Error(errorMessage(error));
    },
    onSuccess: () => {
      setBody('');
      qc.invalidateQueries({ queryKey: ['comments', me.id, id] });
    },
  });
  return (
    <div className="stack">
      {comments.isError && <ErrorState error={comments.error} />}
      {comments.data?.length === 0 && <EmptyState>No comments yet.</EmptyState>}
      {(comments.data ?? []).map(comment => (
        <div key={comment.id} className="comment">
          <strong>{comment.author_name}</strong> <span className="muted">· {formatDateTime(comment.created_at)}</span>
          <p>{comment.body}</p>
        </div>
      ))}
      <form
        className="stack"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          add.mutate();
        }}
      >
        <label>
          Add a comment
          <textarea required rows={3} value={body} onChange={e => setBody(e.target.value)} />
        </label>
        {add.isError && <ErrorState error={add.error} />}
        <div>
          <button className="btn primary" disabled={add.isPending}>
            Post comment
          </button>
        </div>
      </form>
    </div>
  );
}

export function AttachmentsPanel({ id, me }: { id: number; me: PortalUser }) {
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [commentId, setCommentId] = useState('');
  const comments = useComments(id, me);
  const files = useQuery({
    queryKey: ['attachments', me.id, id],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/issues/{id}/attachments/', { params: { path: { id } } });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
  const upload = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error('Choose a file.');
      const form = new FormData();
      form.append('file', file);
      if (commentId) form.append('comment', commentId);
      const headers = new Headers();
      const csrf = readCookie('csrftoken');
      if (csrf) headers.set('X-CSRFToken', csrf);
      const response = await fetch(`/api/issues/${id}/attachments/`, {
        method: 'POST',
        credentials: 'include',
        headers,
        body: form,
      });
      if (!response.ok) throw new Error(`Upload failed (${response.status}).`);
    },
    onSuccess: () => {
      setFile(null);
      setCommentId('');
      qc.invalidateQueries({ queryKey: ['attachments', me.id, id] });
    },
  });
  const comment = (commentRef: number | null | undefined) => {
    const index = (comments.data ?? []).findIndex(item => item.id === commentRef);
    return index >= 0 ? `comment ${index + 1}` : 'a comment';
  };
  return (
    <div className="stack">
      {files.isError && <ErrorState error={files.error} />}
      {files.data?.length === 0 && <EmptyState>No attachments yet.</EmptyState>}
      {(files.data ?? []).map(item => (
        <p key={item.id}>
          <a href={`/api/attachments/${item.id}/download/`}>{item.original_name}</a>
          <span className="muted">
            {' '}
            · {item.quarantine_status}
            {item.comment ? ` · attached to ${comment(item.comment)}` : ''}
          </span>
        </p>
      ))}
      <form
        className="stack"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          upload.mutate();
        }}
      >
        <label>
          File
          <input
            type="file"
            required
            accept=".png,.jpg,.jpeg,.gif,.pdf,.txt,.log,.csv,.zip"
            onChange={e => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <label>
          Attach to comment (optional)
          <select value={commentId} onChange={e => setCommentId(e.target.value)}>
            <option value="">The request itself</option>
            {(comments.data ?? []).map((item, index) => (
              <option key={item.id} value={item.id}>
                Comment {index + 1} by {item.author_name}
              </option>
            ))}
          </select>
        </label>
        {upload.isError && <ErrorState error={upload.error} />}
        <div>
          <button className="btn primary" disabled={upload.isPending}>
            Upload
          </button>
        </div>
      </form>
    </div>
  );
}
