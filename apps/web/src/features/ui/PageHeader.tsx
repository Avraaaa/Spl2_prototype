import type { ReactNode } from 'react';

type Props = { title: string; eyebrow?: string; subtitle?: string; actions?: ReactNode };

export function PageHeader({ title, eyebrow, subtitle, actions }: Props) {
  return (
    <div className="page-head">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {actions && <div className="actions">{actions}</div>}
    </div>
  );
}
