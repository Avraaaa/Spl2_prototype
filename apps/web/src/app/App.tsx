import type { ReactNode } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { ChangePasswordPage } from '../features/auth/ChangePasswordPage';
import { LoginPage } from '../features/auth/LoginPage';
import { CompletePasswordResetPage, ForgotPasswordPage } from '../features/auth/PasswordResetPage';
import { useMe } from '../features/auth/hooks';
import { redirectFor } from '../features/auth/nav';
import { landingFor, type PortalUser } from '../features/auth/roles';
import { Dashboard } from '../features/dashboard/Dashboard';
// ANCHOR P8-T2 imports (audit log)
import { IssueDetailPage } from '../features/issues/IssueDetailPage';
import { IssueDraftPage } from '../features/issues/IssueDraftPage';
import { IssueListPage } from '../features/issues/IssueListPage';
import { ProductsPage } from '../features/issues/ProductsPage';
import { NotificationsPage } from '../features/notifications/NotificationsPage';
// ANCHOR P8-T3 imports (colours)
import { ReportsPage } from '../features/reports/ReportsPage';
// ANCHOR P8-T5 imports (analytics)
import { TasksPage } from '../features/tasks/TasksPage';
// ANCHOR P8-T4 imports (stages, request board)
import { AdminFrame, WorkflowSettingsPage } from '../features/tenants/AdminFrame';
import { UsersAdminPage } from '../features/tenants/UsersAdminPage';
import { LabelAdminPage } from '../features/tenants/LabelAdminPage';
import { IntelligenceAdminPage } from '../features/tenants/IntelligenceAdminPage';
import { Shell } from './Shell';

function Guarded({ user, children }: { user: PortalUser | null | undefined; children: (u: PortalUser) => ReactNode }) {
  const { pathname } = useLocation();
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_password) return <Navigate to="/change-password" replace />;
  const redirect = redirectFor(user, pathname);
  if (redirect) return <Navigate to={redirect} replace />;
  return <Shell me={user}>{children(user)}</Shell>;
}

export function App() {
  const me = useMe();
  if (me.isPending) return <div className="center muted">Loading…</div>;
  if (me.isError) {
    return (
      <div className="center">
        <p className="alert error">The API is unreachable. Is Django running on :8000?</p>
      </div>
    );
  }
  const user = me.data;
  const page = (render: (u: PortalUser) => ReactNode) => <Guarded user={user}>{render}</Guarded>;
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<CompletePasswordResetPage />} />
      <Route path="/change-password" element={<ChangePasswordPage />} />
      <Route path="/account/password" element={user ? <ChangePasswordPage /> : <Navigate to="/login" replace />} />
      <Route path="/" element={page(u => <Dashboard me={u} />)} />
      <Route path="/issues" element={page(u => <IssueListPage me={u} />)} />
      <Route path="/issues/new" element={page(u => <IssueDraftPage me={u} />)} />
      <Route path="/issues/:id/edit" element={page(u => <IssueDraftPage me={u} />)} />
      <Route path="/issues/:id" element={page(u => <IssueDetailPage me={u} />)} />
      <Route path="/awaiting" element={page(u => <IssueListPage me={u} mode="awaiting" />)} />
      <Route path="/queue" element={page(u => <IssueListPage me={u} mode="queue" />)} />
      <Route path="/my-work" element={page(u => <IssueListPage me={u} mode="mine" />)} />
      {/* ANCHOR P8-T4 routes (request board) */}
      <Route path="/tasks" element={page(u => <TasksPage me={u} />)} />
      <Route path="/reports" element={page(u => <ReportsPage me={u} />)} />
      {/* ANCHOR P8-T5 routes (analytics) */}
      <Route path="/notifications" element={page(() => <NotificationsPage />)} />
      <Route path="/admin" element={<Navigate to="/admin/users" replace />} />
      <Route path="/admin/users" element={page(u => <AdminFrame><UsersAdminPage me={u} /></AdminFrame>)} />
      <Route path="/admin/products" element={page(() => <AdminFrame><ProductsPage /></AdminFrame>)} />
      <Route path="/admin/labels" element={page(() => <AdminFrame><LabelAdminPage /></AdminFrame>)} />
      {/* ANCHOR P8-T3 routes (colours) */}
      <Route path="/admin/intelligence" element={page(() => <AdminFrame><IntelligenceAdminPage /></AdminFrame>)} />
      <Route path="/admin/settings" element={page(() => <AdminFrame><WorkflowSettingsPage /></AdminFrame>)} />
      {/* ANCHOR P8-T2 routes (audit log) */}
      <Route path="*" element={<Navigate to={landingFor(user ?? null)} replace />} />
    </Routes>
  );
}
