import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { Login } from './pages/login/Login';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/dashboard/Dashboard';
import { Tenants } from './pages/dashboard/Tenants';

function PrivateRoutes() {
  return (
    <Layout>
      <Routes>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/dashboard/tenants" element={<Tenants />} />
        <Route path="/dashboard/users" element={<div className="p-4">Users - Coming soon</div>} />
        <Route path="/dashboard/documents" element={<div className="p-4">Documents - Coming soon</div>} />
        <Route path="" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Layout>
  );
}

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<PrivateRoutes />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </AuthProvider>
  );
}

export default App;