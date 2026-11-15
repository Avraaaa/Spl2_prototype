import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import { errorMessage } from '../auth/hooks';
import { BellIcon } from '../ui/icons';

const LIST_KEY = ['notifications', 'list'] as const;
const COUNT_KEY = ['notifications', 'count'] as const;

export function useUnreadCount() {
  return useQuery({
    queryKey: COUNT_KEY,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/notifications/unread-count/');
      if (!data) throw new Error(errorMessage(error));
      return data.count;
    },
    refetchInterval: 30_000,
  });
}

export function NotificationBell() {
  const count = useUnreadCount();
  return (
    <Link
      className="icon-button notification-button"
      to="/notifications"
      aria-label={`Notifications${count.data ? `, ${count.data} unread` : ''}`}
    >
      <BellIcon />
      {count.data ? <span>{count.data}</span> : null}
    </Link>
  );
}

export function NotificationsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const list = useQuery({
    queryKey: LIST_KEY,
    queryFn: async () => {
      const { data, error } = await api.GET('/api/notifications/');
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
  });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: LIST_KEY });
    qc.invalidateQueries({ queryKey: COUNT_KEY });
  };
  const read = useMutation({
    mutationFn: async (id: number) => {
      const { data, error } = await api.POST('/api/notifications/{id}/read/', { params: { path: { id } } });
      if (!data) throw new Error(errorMessage(error));
      return data;
    },
    onSuccess: row => {
      refresh();
      if (row.issue) navigate(`/issues/${row.issue}`);
    },
  });
  const readAll = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST('/api/notifications/read-all/');
      if (!data) throw new Error(errorMessage(error));
    },
    onSuccess: refresh,
  });
  return (
    <section className="stack">
      <div className="page-head">
        <div>
          <h1>Notifications</h1>
          <p className="muted">Updates addressed to you.</p>
        </div>
        <button className="btn" disabled={readAll.isPending} onClick={() => readAll.mutate()}>
          Mark all read
        </button>
      </div>
      {list.isError && <p className="alert error">{list.error.message}</p>}
      {(read.isError || readAll.isError) && <p className="alert error">{read.error?.message ?? readAll.error?.message}</p>}
      {list.isPending && <p>Loading notifications…</p>}
      {list.data?.length === 0 && <p className="muted">No notifications yet.</p>}
      {(list.data ?? []).map(row => (
        <div className="card notification-card" key={row.id}>
          <strong>{row.title}</strong>
          {!row.read_at && <span className="badge tone-info">Unread</span>}
          <p>{row.body}</p>
          <small className="muted">{new Date(row.created_at).toLocaleString()}</small>
          {row.issue ? (
            <button className="btn small" disabled={read.isPending} onClick={() => read.mutate(row.id)}>
              View request
            </button>
          ) : (
            !row.read_at && (
              <button className="btn small" disabled={read.isPending} onClick={() => read.mutate(row.id)}>
                Mark read
              </button>
            )
          )}
        </div>
      ))}
    </section>
  );
}
