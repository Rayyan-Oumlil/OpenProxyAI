import { Navigate, Route, Routes } from "react-router-dom";

import { DashboardPage } from "./features/dashboard/DashboardPage";
import { AdminLayout } from "./features/layout/AdminLayout";
import { LogsPage } from "./features/logs/LogsPage";
import { ApiKeysPage } from "./features/keys/ApiKeysPage";
import { LoginPage } from "./features/auth/LoginPage";
import { OrganizationSettingsPage } from "./features/placeholder/OrganizationSettingsPage";
import { UsersRolesPage } from "./features/placeholder/UsersRolesPage";
import { useAuth } from "./state/AuthContext";

export function App() {
  const { token } = useAuth();

  if (!token) {
    return <LoginPage />;
  }

  return (
    <Routes>
      <Route path="/" element={<AdminLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="logs" element={<LogsPage />} />
        <Route path="api-keys" element={<ApiKeysPage />} />
        <Route path="users-roles" element={<UsersRolesPage />} />
        <Route path="organization-settings" element={<OrganizationSettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

