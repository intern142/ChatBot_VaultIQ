import { Routes, Route, Navigate } from 'react-router-dom';
import { RequireAuth, RequireRole } from './guards';
import { PATHS } from './paths';
import LoginPage from '../pages/LoginPage';
import NotFoundPage from '../pages/NotFoundPage';
import DocumentsPage from '../pages/tenant/DocumentsPage';
import StoragePage from '../pages/tenant/StoragePage';
import TenantsPage from '../pages/operator/TenantsPage';
import AuditLogPage from '../pages/operator/AuditLogPage';
import UserManagementPage from '../pages/UserManagementPage';
import PasswordResetPage from '../pages/PasswordResetPage';
import SearchPage from '../pages/SearchPage';
import AnswersPage from '../pages/AnswersPage';
import { AppShell } from '../components/layout/AppShell';

function PrivateLayout() {
  return (
    <RequireAuth>
      <AppShell />
    </RequireAuth>
  );
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route path={PATHS.login} element={<LoginPage />} />
      <Route path={PATHS.resetPassword} element={<PasswordResetPage />} />
      <Route element={<PrivateLayout />}>
        <Route
          path={PATHS.home}
          element={
            <RequireRole allowedRoles={['super_admin']}>
              <Navigate to={PATHS.tenants} replace />
            </RequireRole>
          }
        />
        <Route
          path={PATHS.documents}
          element={
            <RequireRole allowedRoles={['client_admin', 'employee']}>
              <DocumentsPage />
            </RequireRole>
          }
        />
        <Route
          path={PATHS.storage}
          element={
            <RequireRole allowedRoles={['client_admin']}>
              <StoragePage />
            </RequireRole>
          }
        />
        <Route
          path={PATHS.tenants}
          element={
            <RequireRole allowedRoles={['super_admin']}>
              <TenantsPage />
            </RequireRole>
          }
        />
        <Route
          path={PATHS.audit(':tenantId')}
          element={
            <RequireRole allowedRoles={['super_admin']}>
              <AuditLogPage />
            </RequireRole>
          }
        />
        <Route
          path={PATHS.users}
          element={
            <RequireRole allowedRoles={['client_admin']}>
              <UserManagementPage />
            </RequireRole>
          }
        />
        <Route
          path={PATHS.search}
          element={
            <RequireRole allowedRoles={['client_admin', 'employee']}>
              <SearchPage />
            </RequireRole>
          }
        />
        <Route
          path={PATHS.answers}
          element={
            <RequireRole allowedRoles={['client_admin', 'employee']}>
              <AnswersPage />
            </RequireRole>
          }
        />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}