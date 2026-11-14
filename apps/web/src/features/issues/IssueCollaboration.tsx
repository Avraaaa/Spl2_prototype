import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, readCookie } from '../../api/client';
import { errorMessage } from '../auth/hooks';
import { hasRole, type PortalUser } from '../auth/roles';

export function IssueCollaboration({ id, me }: { id: number; me: PortalUser }) {
  const qc = useQueryClient();
  const staff = hasRole(me, 'DATASOFT_ADMIN') || hasRole(me, 'SUPPORT_AGENT');
  const [body, setBody] = useState('');
  const [note, setNote] = useState('');
  const [title, setTitle] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [commentId, setCommentId] = useState('');
  const comments = useQuery({ queryKey: ['comments', me.id, id], queryFn: async () => {
    const { data, error } = await api.GET('/api/issues/{id}/comments/', { params: { path: { id } } });
    if (!data) throw new Error(errorMessage(error));
    return data;
  } });
  const files = useQuery({ queryKey: ['attachments', me.id, id], queryFn: async () => {
    const { data, error } = await api.GET('/api/issues/{id}/attachments/', { params: { path: { id } } });
    if (!data) throw new Error(errorMessage(error));
    return data;
  } });
  const notes = useQuery({ queryKey: ['internal-notes', me.id, id], enabled: staff, queryFn: async () => {
    const { data, error } = await api.GET('/api/issues/{id}/internal-notes/', { params: { path: { id } } });
    if (!data) throw new Error(errorMessage(error));
    return data;
  } });
  const tasks = useQuery({ queryKey: ['tasks', me.id], enabled: staff, queryFn: async () => {
    const { data, error } = await api.GET('/api/tasks/');
    if (!data) throw new Error(errorMessage(error));
    return data;
  } });
  const addComment = useMutation({ mutationFn: async () => {
    const { data, error } = await api.POST('/api/issues/{id}/comments/', { params: { path: { id } }, body: { body } });
    if (!data) throw new Error(errorMessage(error));
  }, onSuccess: () => { setBody(''); qc.invalidateQueries({ queryKey: ['comments', me.id, id] }); } });
  const addNote = useMutation({ mutationFn: async () => {
    const { data, error } = await api.POST('/api/issues/{id}/internal-notes/', { params: { path: { id } }, body: { body: note } });
    if (!data) throw new Error(errorMessage(error));
  }, onSuccess: () => { setNote(''); qc.invalidateQueries({ queryKey: ['internal-notes', me.id, id] }); } });
  const addTask = useMutation({ mutationFn: async () => {
    const { data, error } = await api.POST('/api/tasks/', { body: { issue: id, title } });
    if (!data) throw new Error(errorMessage(error));
  }, onSuccess: () => { setTitle(''); qc.invalidateQueries({ queryKey: ['tasks', me.id] }); } });
  const upload = useMutation({ mutationFn: async () => {
    if (!file) throw new Error('Choose a file.');
    const form = new FormData();
    form.append('file', file);
    if (commentId) form.append('comment', commentId);
    const headers = new Headers();
    const csrf = readCookie('csrftoken');
    if (csrf) headers.set('X-CSRFToken', csrf);
    const response = await fetch(`/api/issues/${id}/attachments/`, { method: 'POST', credentials: 'include', headers, body: form });
    if (!response.ok) throw new Error(`Upload failed (${response.status}).`);
  }, onSuccess: () => { setFile(null); setCommentId(''); qc.invalidateQueries({ queryKey: ['attachments', me.id, id] }); } });
  const error = comments.error ?? files.error ?? notes.error ?? tasks.error ?? addComment.error ?? addNote.error ?? addTask.error ?? upload.error;
  return <>
    <div className="card stack"><h3>Comments</h3>{(comments.data ?? []).map(comment => <div key={comment.id}><strong>{comment.author_name}</strong> · {new Date(comment.created_at).toLocaleString()}<p>{comment.body}</p></div>)}
      <form onSubmit={(e: FormEvent) => { e.preventDefault(); addComment.mutate(); }}><label>Add a comment<textarea required value={body} onChange={e => setBody(e.target.value)} /></label><button className="btn primary" disabled={addComment.isPending}>Post comment</button></form>
    </div>
    <div className="card stack"><h3>Attachments</h3>{(files.data ?? []).map(item => <p key={item.id}><a href={`/api/attachments/${item.id}/download/`}>{item.original_name}</a> · {item.quarantine_status}{item.comment && <> · comment #{item.comment}</>}</p>)}
      <form onSubmit={(e: FormEvent) => { e.preventDefault(); upload.mutate(); }}><label>File<input type="file" required accept=".png,.jpg,.jpeg,.gif,.pdf,.txt,.log,.csv,.zip" onChange={e => setFile(e.target.files?.[0] ?? null)} /></label><label>Attach to comment (optional)<select value={commentId} onChange={e => setCommentId(e.target.value)}><option value="">Issue</option>{(comments.data ?? []).map(item => <option key={item.id} value={item.id}>Comment #{item.id}</option>)}</select></label><button className="btn primary" disabled={upload.isPending}>Upload</button></form>
    </div>
    {staff && <div className="card stack"><h3>Internal</h3><h4>Notes</h4>{(notes.data ?? []).map(item => <p key={item.id}>{item.author_name}: {item.body}</p>)}
      <form onSubmit={(e: FormEvent) => { e.preventDefault(); addNote.mutate(); }}><label>New internal note<textarea required value={note} onChange={e => setNote(e.target.value)} /></label><button className="btn" disabled={addNote.isPending}>Save note</button></form>
      <h4>Linked tasks</h4>{(tasks.data ?? []).filter(task => task.issue === id).map(task => <p key={task.id}>{task.title} · {task.status}</p>)}
      <form onSubmit={(e: FormEvent) => { e.preventDefault(); addTask.mutate(); }}><label>Task title<input required maxLength={200} value={title} onChange={e => setTitle(e.target.value)} /></label><button className="btn" disabled={addTask.isPending}>Create task</button></form><Link to="/tasks">Open task board</Link>
    </div>}
    {error && <p className="alert error">{error.message}</p>}
  </>;
}
