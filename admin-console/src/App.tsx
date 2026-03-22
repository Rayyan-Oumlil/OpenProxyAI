import { Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";

import { DashboardPage } from "./features/dashboard/DashboardPage";
import { AdminLayout } from "./features/layout/AdminLayout";
import { LogsPage } from "./features/logs/LogsPage";
import { ApiKeysPage } from "./features/keys/ApiKeysPage";
import { LoginPage } from "./features/auth/LoginPage";
import { SignupPage } from "./features/auth/SignupPage";
import { SSOCallbackPage } from "./features/auth/SSOCallbackPage";
import { OrganizationSettingsPage } from "./features/settings/OrganizationSettingsPage";
import { UsersRolesPage } from "./features/users/UsersRolesPage";
import { TeamsPage } from "./features/teams/TeamsPage";
import { ProviderKeysPage } from "./features/providerkeys/ProviderKeysPage";
import { ExperimentsPage } from "./features/experiments/ExperimentsPage";
import { OnboardingModal } from "./features/onboarding/OnboardingModal";
import { PolicyConfigPage } from "./features/policy/PolicyConfigPage";
import { AuditLogPage } from "./features/audit/AuditLogPage";
import { BillingPage } from "./features/billing/BillingPage";
import { PlaygroundPage } from "./features/playground/PlaygroundPage";
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
        <Routes>
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/sso-callback" element={<SSOCallbackPage />} />
          <Route path="*" element={<LoginPage />} />
        </Routes>
      ) : (
        <>
        <OnboardingModal />
        <Routes>
          <Route path="/" element={<AdminLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="logs" element={<LogsPage />} />
            <Route path="api-keys" element={<ApiKeysPage />} />
            <Route path="provider-keys" element={<ProviderKeysPage />} />
            <Route path="experiments" element={<ExperimentsPage />} />
            <Route path="policy" element={<PolicyConfigPage />} />
            <Route path="teams" element={<TeamsPage />} />
            <Route path="users-roles" element={<UsersRolesPage />} />
            <Route path="organization-settings" element={<OrganizationSettingsPage />} />
            <Route path="billing" element={<BillingPage />} />
            <Route path="audit" element={<AuditLogPage />} />
            <Route path="playground" element={<PlaygroundPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </>
      )}
    </>
  );
}
