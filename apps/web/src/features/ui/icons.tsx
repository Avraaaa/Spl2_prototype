import type { SVGProps } from 'react';

type IconProps = SVGProps<SVGSVGElement>;

function Icon({ children, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      {children}
    </svg>
  );
}

export const DashboardIcon = (props: IconProps) => <Icon {...props}><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></Icon>;
export const RequestsIcon = (props: IconProps) => <Icon {...props}><path d="M7 3h10l3 3v15H4V3h3Z" /><path d="M8 9h8M8 13h8M8 17h5" /></Icon>;
export const PlusIcon = (props: IconProps) => <Icon {...props}><path d="M12 5v14M5 12h14" /></Icon>;
export const VerifyIcon = (props: IconProps) => <Icon {...props}><path d="m4 12 5 5L20 6" /></Icon>;
export const TasksIcon = (props: IconProps) => <Icon {...props}><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M8 9h8M8 13h8M8 17h5" /></Icon>;
export const ReportsIcon = (props: IconProps) => <Icon {...props}><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></Icon>;
export const AdminIcon = (props: IconProps) => <Icon {...props}><circle cx="12" cy="8" r="3" /><path d="M5 21a7 7 0 0 1 14 0M19 4v4M17 6h4" /></Icon>;
export const BellIcon = (props: IconProps) => <Icon {...props}><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" /></Icon>;
export const MenuIcon = (props: IconProps) => <Icon {...props}><path d="M4 7h16M4 12h16M4 17h16" /></Icon>;
export const LockIcon = (props: IconProps) => <Icon {...props}><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></Icon>;
export const LogoutIcon = (props: IconProps) => <Icon {...props}><path d="M10 17l5-5-5-5M15 12H3M21 3v18h-7" /></Icon>;

export function NavIcon({ label }: { label: string }) {
  if (label === 'Dashboard') return <DashboardIcon />;
  if (label === 'New request') return <PlusIcon />;
  if (label.includes('verification')) return <VerifyIcon />;
  if (label.includes('Tasks')) return <TasksIcon />;
  if (label === 'Reports') return <ReportsIcon />;
  if (label === 'Admin') return <AdminIcon />;
  return <RequestsIcon />;
}
