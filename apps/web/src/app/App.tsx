import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';

export function App() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const { data, error } = await api.GET('/api/health/');
      if (error || !data) throw new Error('API unavailable');
      return data;
    },
  });
  return (
    <main className="shell">
      <header><strong>DataSoft</strong><span>Service Request Portal</span></header>
      <section className="panel">
        <p className="eyebrow">PROJECT FOUNDATION</p>
        <h1>Service requests, in one accountable workflow.</h1>
        <p>This screen verifies the frontend-to-Django connection through the generated OpenAPI client.</p>
        <p role="status">API: {health.isPending ? 'checking…' : health.isError ? 'offline' : `${health.data.status} (${health.data.stage})`}</p>
        <small>No live banking data belongs in this prototype.</small>
      </section>
    </main>
  );
}
