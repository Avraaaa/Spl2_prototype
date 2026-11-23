import { NavLink } from 'react-router-dom';
import type { ReactNode } from 'react';
import { PageHeader } from '../ui/PageHeader';
import { WorkflowSettingsPanel } from '../workflow/WorkflowActions';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import { errorMessage } from '../auth/hooks';
import { useState } from 'react';

const SECTIONS = [
  { to: '/admin/users', label: 'Users & banks' },
  { to: '/admin/products', label: 'Products' },
  { to: '/admin/labels', label: 'Issue labels' },
  // ANCHOR P8-T3 admin section (colours)
  { to: '/admin/intelligence', label: 'Intelligence & privacy' },
  // ANCHOR P8-T2 admin section (audit log)
  { to: '/admin/settings', label: 'Workflow settings' },
  // ANCHOR P8-T4 admin section (stages)
];

/** Administrator-only sub-navigation wrapped around each admin page. */
export function AdminFrame({ children }: { children: ReactNode }) {
  return (
    <div className="stack">
      <nav className="subnav" aria-label="Admin sections">
        {SECTIONS.map(section => (
          <NavLink key={section.to} to={section.to}>
            {section.label}
          </NavLink>
        ))}
      </nav>
      {children}
    </div>
  );
}

export function WorkflowSettingsPage() {
  const qc = useQueryClient();
  const settings = useQuery({ queryKey: ['response-due-periods'], queryFn: async () => { const { data, error } = await api.GET('/api/admin/response-due-periods/'); if (!data) throw new Error(errorMessage(error)); return data; } });
  const [periods, setPeriods] = useState<Record<string, number> | null>(null);
  const save = useMutation({ mutationFn: async () => { const { data, error } = await api.PUT('/api/admin/response-due-periods/', { body: { periods: periods ?? settings.data?.periods ?? {} } }); if (!data) throw new Error(errorMessage(error)); return data; }, onSuccess: data => { setPeriods(data.periods); qc.invalidateQueries({ queryKey: ['response-due-periods'] }); qc.invalidateQueries({ queryKey: ['reports'] }); } });
  return (
    <section className="stack">
      <PageHeader title="Workflow settings" subtitle="Policies that apply to every bank." />
      <WorkflowSettingsPanel />
      <div className="card form-grid"><h2>Response due periods</h2><p>Calendar days allowed for a first response to a submitted request.</p>{(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const).map(priority => <label key={priority}>{priority} priority (days)<input type="number" min={0} max={3650} value={(periods ?? settings.data?.periods)?.[priority] ?? ''} onChange={event => setPeriods(current => ({ ...(current ?? settings.data?.periods ?? {}), [priority]: Number(event.target.value) }))} /></label>)}{settings.isError && <p role="alert" className="alert error">{settings.error.message}</p>}{save.isError && <p role="alert" className="alert error">{save.error.message}</p>}<button className="btn primary" disabled={save.isPending || !settings.data} onClick={() => save.mutate()}>Save response periods</button></div>
    </section>
  );
}
