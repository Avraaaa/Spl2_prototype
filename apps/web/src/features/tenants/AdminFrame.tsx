import { NavLink } from 'react-router-dom';
import type { ReactNode } from 'react';
import { PageHeader } from '../ui/PageHeader';
import { WorkflowSettingsPanel } from '../workflow/WorkflowActions';

const SECTIONS = [
  { to: '/admin/users', label: 'Users & banks' },
  { to: '/admin/products', label: 'Products' },
  { to: '/admin/settings', label: 'Workflow settings' },
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
  return (
    <section className="stack">
      <PageHeader title="Workflow settings" subtitle="Policies that apply to every bank." />
      <WorkflowSettingsPanel />
    </section>
  );
}
