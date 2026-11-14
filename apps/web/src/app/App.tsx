import { useQuery } from '@tanstack/react-query';

export function App() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const response = await fetch('/api/health/', { credentials: 'include' });
      if (!response.ok) throw new Error('API unavailable');
      return (await response.json()) as { status: string; stage: string };
    },
  });
  return (
    <main className="shell">
      <header><strong>DataSoft</strong><span>Service Request Portal</span></header>
      <section className="panel">
        <p className="eyebrow">PROJECT FOUNDATION</p>
        <h1>Service requests, in one accountable workflow.</h1>
        <p>This screen verifies the frontend-to-Django connection. The authenticated portal, bank-scoped issue dashboard and lifecycle are implemented in planned phases.</p>
        <p role="status">API: {health.isPending ? 'checking…' : health.isError ? 'offline' : `${health.data.status} (${health.data.stage})`}</p>
        <small>No live banking data belongs in this prototype.</small>
      </section>
    </main>
  );
}
