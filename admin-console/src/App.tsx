import { Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";

import { DashboardPage } from "./features/dashboard/DashboardPage";
import { AdminLayout } from "./features/layout/AdminLayout";
import { LogsPage } from "./features/logs/LogsPage";
import { ApiKeysPage } from "./features/keys/ApiKeysPage";
import { LoginPage } from "./features/auth/LoginPage";
import { OrganizationSettingsPage } from "./features/placeholder/OrganizationSettingsPage";
import { UsersRolesPage } from "./features/placeholder/UsersRolesPage";
import { ProviderKeysPage } from "./features/providerkeys/ProviderKeysPage";
import { OnboardingModal } from "./features/onboarding/OnboardingModal";
import { PolicyConfigPage } from "./features/policy/PolicyConfigPage";
import { AuditLogPage } from "./features/audit/AuditLogPage";
import { useAuth } from "./state/AuthContext";

export function App() {
  const { token, isRestoring } = useAuth();

  if (isRestoring) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          background: "var(--bg)",
        }}
      >
        <div className="loader" />
      </div>
    );
  }

  return (
    <>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: "var(--surface)",
            border: "1px solid var(--line)",
            color: "var(--text)",
            fontFamily: "Space Grotesk, sans-serif",
          },
        }}
      />
      {!token ? (
        <LoginPage />
      ) : (
        <>
        <OnboardingModal />
        <Routes>
          <Route path="/" element={<AdminLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="logs" element={<LogsPage />} />
            <Route path="api-keys" element={<ApiKeysPage />} />
            <Route path="provider-keys" element={<ProviderKeysPage />} />
            <Route path="policy" element={<PolicyConfigPage />} />
            <Route path="users-roles" element={<UsersRolesPage />} />
            <Route path="organization-settings" element={<OrganizationSettingsPage />} />
            <Route path="audit" element={<AuditLogPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </>
      )}
    </>
  );
}
