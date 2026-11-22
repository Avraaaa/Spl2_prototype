import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import { errorMessage } from '../auth/hooks';
import { isStaff } from '../auth/nav';
import type { PortalUser } from '../auth/roles';
import { Dropzone } from '../ui/Dropzone';
import { EmptyState, ErrorState } from '../ui/EmptyState';
import { formatDateTime } from '../ui/format';
import {
  ATTACHMENT_ACCEPT,
  attachmentKind,
  formatFileSize,
  uploadAttachment,
  validateAttachment,
} from './attachments';

type QueuedFile = {
  key: string;
  file: File;
  status: 'ready' | 'uploading' | 'uploaded' | 'error';
  validationError?: string;
  error?: string;
};

function queuedFiles(files: File[]): QueuedFile[] {
  return files.map((file, index) => {
    const validationError = validateAttachment(file) ?? undefined;
    return {
      key: `${file.name}-${file.size}-${file.lastModified}-${Date.now()}-${index}`,
      file,
      status: validationError ? 'error' : 'ready',
      validationError,
      error: validationError,
    };
  });
}

function UploadQueue({
  files,
  busy,
  remove,
}: {
  files: QueuedFile[];
  busy: boolean;
  remove: (key: string) => void;
}) {
  if (files.length === 0) return null;
  return (
    <ul className="upload-queue" aria-label="Files selected for upload">
      {files.map(item => (
        <li key={item.key} className={item.status === 'error' ? 'has-error' : ''}>
          <span className={`file-icon kind-${attachmentKind(item.file.name)}`} aria-hidden="true" />
          <span className="file-summary">
            <strong>{item.file.name}</strong>
            <span className="muted">
              {formatFileSize(item.file.size)} · {item.status}
            </span>
            {item.error && <span className="field-error">{item.error}</span>}
          </span>
          <button type="button" className="btn small ghost" disabled={busy} onClick={() => remove(item.key)}>
            Remove
          </button>
        </li>
      ))}
    </ul>
  );
}

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
  const [files, setFiles] = useState<QueuedFile[]>([]);
  const [postedCommentId, setPostedCommentId] = useState<number | null>(null);
  const [notice, setNotice] = useState('');
  const comments = useComments(id, me);
  const updateFile = (key: string, change: Partial<QueuedFile>) => {
    setFiles(current => current.map(item => (item.key === key ? { ...item, ...change } : item)));
  };
  const add = useMutation({
    mutationFn: async () => {
      setNotice('');
      if (files.some(file => file.validationError)) throw new Error('Remove invalid attachments before posting.');
      let commentId = postedCommentId;
      if (!commentId) {
        const { data, error } = await api.POST('/api/issues/{id}/comments/', {
          params: { path: { id } },
          body: { body },
        });
        if (!data) throw new Error(errorMessage(error));
        commentId = data.id;
        setPostedCommentId(commentId);
        setBody('');
        qc.invalidateQueries({ queryKey: ['comments', me.id, id] });
      }
      let failed = false;
      for (const item of files) {
        if (item.status === 'uploaded') continue;
        updateFile(item.key, { status: 'uploading', error: undefined });
        try {
          await uploadAttachment(id, item.file, commentId);
          updateFile(item.key, { status: 'uploaded' });
        } catch (error) {
          failed = true;
          updateFile(item.key, {
            status: 'error',
            error: error instanceof Error ? error.message : 'Upload failed.',
          });
        }
      }
      if (failed) throw new Error('Comment posted, but one or more attachments failed. Retry to upload them.');
    },
    onSuccess: () => {
      setNotice(files.length ? 'Comment and attachments posted.' : 'Comment posted.');
      setBody('');
      setFiles([]);
      setPostedCommentId(null);
      qc.invalidateQueries({ queryKey: ['comments', me.id, id] });
      qc.invalidateQueries({ queryKey: ['attachments', me.id, id] });
    },
  });
  return (
    <div className="stack">
      {comments.isError && <ErrorState error={comments.error} />}
      {notice && <p className="alert success">{notice}</p>}
      {comments.data?.length === 0 && <EmptyState>No comments yet.</EmptyState>}
      {(comments.data ?? []).map(comment => (
        <div key={comment.id} className="comment">
          <strong>{comment.author_name}</strong> <span className="muted">· {formatDateTime(comment.created_at)}</span>
          <p>{comment.body}</p>
        </div>
      ))}
      <form
        className="stack"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          add.mutate();
        }}
      >
        <label>
          Add a comment
          <textarea
            required={!postedCommentId}
            disabled={Boolean(postedCommentId)}
            rows={3}
            value={body}
            onChange={event => setBody(event.target.value)}
          />
        </label>
        <Dropzone
          accept={ATTACHMENT_ACCEPT}
          disabled={add.isPending}
          onFiles={selected => setFiles(current => [...current, ...queuedFiles(selected)])}
          helper="Optional: attach PNG, JPG, GIF, PDF, TXT, LOG, CSV, ZIP, DOCX, XLSX or PPTX files up to 10 MB."
          label="Attach files to this comment"
        />
        <UploadQueue
          files={files}
          busy={add.isPending}
          remove={key => setFiles(current => current.filter(file => file.key !== key))}
        />
        {add.isError && <ErrorState error={add.error} />}
        <div>
          <button className="btn primary" disabled={add.isPending || (!body.trim() && !postedCommentId)}>
            {add.isPending ? 'Posting…' : postedCommentId ? 'Retry attachments' : 'Post comment'}
          </button>
        </div>
      </form>
    </div>
  );
}

export function AttachmentsPanel({ id, me }: { id: number; me: PortalUser }) {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<QueuedFile[]>([]);
  const [commentId, setCommentId] = useState('');
  const [notice, setNotice] = useState('');
  const comments = useComments(id, me);
  const files = useQuery({
    queryKey: ['attachments', me.id, id],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/issues/{id}/attachments/', { params: { path: { id } } });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
  const updateFile = (key: string, change: Partial<QueuedFile>) => {
    setSelected(current => current.map(item => (item.key === key ? { ...item, ...change } : item)));
  };
  const upload = useMutation({
    mutationFn: async () => {
      setNotice('');
      if (selected.length === 0) throw new Error('Choose at least one file.');
      if (selected.some(file => file.validationError)) throw new Error('Remove invalid files before uploading.');
      let failed = false;
      for (const item of selected) {
        if (item.status === 'uploaded') continue;
        updateFile(item.key, { status: 'uploading', error: undefined });
        try {
          await uploadAttachment(id, item.file, commentId ? Number(commentId) : undefined);
          updateFile(item.key, { status: 'uploaded' });
        } catch (error) {
          failed = true;
          updateFile(item.key, {
            status: 'error',
            error: error instanceof Error ? error.message : 'Upload failed.',
          });
        }
      }
      if (failed) throw new Error('Some files could not be uploaded. Successful files are already saved.');
    },
    onSuccess: () => {
      setNotice(`${selected.length} file${selected.length === 1 ? '' : 's'} uploaded.`);
      setSelected([]);
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
      {notice && <p className="alert success">{notice}</p>}
      {files.data?.length === 0 && <EmptyState>No attachments yet.</EmptyState>}
      <div className="attachment-list">
        {(files.data ?? []).map(item => {
          const download = `/api/attachments/${item.id}/download/`;
          const image = item.content_type.startsWith('image/');
          return (
            <article key={item.id} className="attachment-item">
              {image ? (
                <img className="attachment-thumb" src={download} alt="" />
              ) : (
                <span className={`file-icon large kind-${attachmentKind(item.original_name)}`} aria-hidden="true" />
              )}
              <div className="file-summary">
                <a href={download}>{item.original_name}</a>
                <span className="muted">
                  {formatFileSize(item.size)} · Uploaded by{' '}
                  {item.uploaded_by === me.id ? me.full_name : isStaff(me) ? 'a client user' : 'DataSoft staff'}
                  {' · '}
                  {formatDateTime(item.created_at)}
                </span>
                <span className="attachment-tags">
                  {item.comment ? <span className="chip">Attached to {comment(item.comment)}</span> : null}
                  <span className={`chip ${item.quarantine_status === 'CLEAN' ? '' : 'warn'}`}>
                    {item.quarantine_status === 'CLEAN' ? 'Scan clean' : `Attachment ${item.quarantine_status.toLowerCase()}`}
                  </span>
                </span>
              </div>
            </article>
          );
        })}
      </div>
      <form
        className="stack attachment-upload"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          upload.mutate();
        }}
      >
        <Dropzone
          accept={ATTACHMENT_ACCEPT}
          disabled={upload.isPending}
          onFiles={picked => setSelected(current => [...current, ...queuedFiles(picked)])}
          helper="PNG, JPG, GIF, PDF, TXT, LOG, CSV, ZIP, DOCX, XLSX or PPTX. Maximum 10 MB per file."
        />
        <UploadQueue
          files={selected}
          busy={upload.isPending}
          remove={key => setSelected(current => current.filter(file => file.key !== key))}
        />
        <label>
          Attach to comment (optional)
          <select value={commentId} onChange={event => setCommentId(event.target.value)}>
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
          <button className="btn primary" disabled={upload.isPending || selected.length === 0}>
            {upload.isPending ? 'Uploading…' : `Upload ${selected.length || ''} file${selected.length === 1 ? '' : 's'}`}
          </button>
        </div>
      </form>
    </div>
  );
}
