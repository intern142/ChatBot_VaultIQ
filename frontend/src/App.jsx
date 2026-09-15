import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/Layout/Layout';
import Login from './pages/Login';
import Register from './pages/Register';
import Chat from './pages/employee/Chat';
import History from './pages/employee/History';
import EmployeeDashboard from './pages/employee/Dashboard';
import Dashboard from './pages/client-admin/Dashboard';
import Documents from './pages/client-admin/Documents';
import Staff from './pages/client-admin/Staff';
import Settings from './pages/client-admin/Settings';
import SuperDashboard from './pages/super-admin/Dashboard';
import SuperDocuments from './pages/super-admin/Documents';
import Tenants from './pages/super-admin/Tenants';
import Health from './pages/super-admin/Health';
import SuperSettings from './pages/super-admin/Settings';
import { ProtectedRoute } from './components/ProtectedRoute';

const ROLE_HOME = {
  employee: '/employee/dashboard',
  'client-admin': '/admin/dashboard',
  'super-admin': '/super/tenants',
};

function AppRoutes() {
  const { role, isAuthenticated } = useAuth();

  const defaultRedirect = {
    employee: '/employee/dashboard',
    'client-admin': '/admin/dashboard',
    'super-admin': '/super/tenants',
  };

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route
        path="/"
        element={
          isAuthenticated ? (
            <Layout />
          ) : (
            <Navigate to="/login" replace />
          )
        }
      >
        <Route index element={<Navigate to={defaultRedirect[role]} replace />} />

        <Route
          path="employee"
          element={
            <ProtectedRoute allowedRoles={['employee']}>
              <Outlet />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<EmployeeDashboard />} />
          <Route path="chat" element={<Chat />} />
          <Route path="history" element={<History />} />
        </Route>

        <Route
          path="admin"
          element={
            <ProtectedRoute allowedRoles={['client-admin']}>
              <Outlet />
            </ProtectedRoute>
          }
        >
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="documents" element={<Documents />} />
          <Route path="staff" element={<Staff />} />
          <Route path="settings" element={<Settings />} />
        </Route>

        <Route
          path="super"
          element={
            <ProtectedRoute allowedRoles={['super-admin']}>
              <Outlet />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="tenants" replace />} />
          <Route path="dashboard" element={<SuperDashboard />} />
          <Route path="documents" element={<SuperDocuments />} />
          <Route path="tenants" element={<Tenants />} />
          <Route path="health" element={<Health />} />
          <Route path="settings" element={<SuperSettings />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;