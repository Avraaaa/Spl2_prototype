import { readCookie } from '../../api/client';

export const MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024;
export const ATTACHMENT_ACCEPT =
  '.png,.jpg,.jpeg,.gif,.pdf,.txt,.log,.csv,.zip,.docx,.xlsx,.pptx';

const ALLOWED_EXTENSIONS = new Set(ATTACHMENT_ACCEPT.split(','));

export type AttachmentKind = 'image' | 'pdf' | 'document' | 'sheet' | 'slides' | 'text' | 'archive' | 'file';

export type AttachmentCandidate = {
  name: string;
  size: number;
};

export function validateAttachment(file: AttachmentCandidate): string | null {
  const dot = file.name.lastIndexOf('.');
  const extension = dot >= 0 ? file.name.slice(dot).toLowerCase() : '';
  if (!ALLOWED_EXTENSIONS.has(extension)) {
    return 'Choose one of the allowed types: PNG, JPG, GIF, PDF, TXT, LOG, CSV, ZIP, DOCX, XLSX or PPTX.';
  }
  if (file.size === 0) return 'The file is empty.';
  if (file.size > MAX_ATTACHMENT_SIZE) return 'The file is larger than the 10 MB limit.';
  return null;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Number((bytes / 1024).toFixed(1))} KB`;
  return `${Number((bytes / (1024 * 1024)).toFixed(1))} MB`;
}

export function attachmentKind(name: string): AttachmentKind {
  const extension = name.slice(name.lastIndexOf('.')).toLowerCase();
  if (['.png', '.jpg', '.jpeg', '.gif'].includes(extension)) return 'image';
  if (extension === '.pdf') return 'pdf';
  if (extension === '.docx') return 'document';
  if (extension === '.xlsx') return 'sheet';
  if (extension === '.pptx') return 'slides';
  if (['.txt', '.log', '.csv'].includes(extension)) return 'text';
  if (extension === '.zip') return 'archive';
  return 'file';
}

export function attachmentServerError(payload: unknown, status: number): string {
  if (payload && typeof payload === 'object') {
    const fields = payload as Record<string, unknown>;
    const file = fields.file;
    if (typeof file === 'string') return file;
    if (Array.isArray(file) && typeof file[0] === 'string') return file[0];
    if (typeof fields.detail === 'string') return fields.detail;
  }
  return `Upload failed (${status}).`;
}

export async function uploadAttachment(issueId: number, file: File, commentId?: number): Promise<void> {
  const form = new FormData();
  form.append('file', file);
  if (commentId) form.append('comment', String(commentId));
  const headers = new Headers();
  const csrf = readCookie('csrftoken');
  if (csrf) headers.set('X-CSRFToken', csrf);
  const response = await fetch(`/api/issues/${issueId}/attachments/`, {
    method: 'POST',
    credentials: 'include',
    headers,
    body: form,
  });
  if (response.ok) return;
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    // A proxy or server failure may return HTML; the status fallback remains useful.
  }
  throw new Error(attachmentServerError(payload, response.status));
}
