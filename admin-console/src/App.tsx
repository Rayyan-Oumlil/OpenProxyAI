import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";

import { AdminLayout } from "./features/layout/AdminLayout";
import { LoadingState } from "./components/LoadingState";
import { OnboardingModal } from "./features/onboarding/OnboardingModal";
import { useAuth } from "./state/AuthContext";

// Each page is its own chunk: the console no longer ships every screen (and recharts) up front.
const DashboardPage = lazy(() => import("./features/dashboard/DashboardPage").then((m) => ({ default: m.DashboardPage })));
const RequestTracePage = lazy(() => import("./features/logs/RequestTracePage").then((m) => ({ default: m.RequestTracePage })));
const LogsPage = lazy(() => import("./features/logs/LogsPage").then((m) => ({ default: m.LogsPage })));
const ApiKeysPage = lazy(() => import("./features/keys/ApiKeysPage").then((m) => ({ default: m.ApiKeysPage })));
const LoginPage = lazy(() => import("./features/auth/LoginPage").then((m) => ({ default: m.LoginPage })));
const SignupPage = lazy(() => import("./features/auth/SignupPage").then((m) => ({ default: m.SignupPage })));
const SSOCallbackPage = lazy(() => import("./features/auth/SSOCallbackPage").then((m) => ({ default: m.SSOCallbackPage })));
const AcceptInvitePage = lazy(() => import("./features/auth/AcceptInvitePage").then((m) => ({ default: m.AcceptInvitePage })));
const OrganizationSettingsPage = lazy(() => import("./features/settings/OrganizationSettingsPage").then((m) => ({ default: m.OrganizationSettingsPage })));
const UsersRolesPage = lazy(() => import("./features/users/UsersRolesPage").then((m) => ({ default: m.UsersRolesPage })));
const TeamsPage = lazy(() => import("./features/teams/TeamsPage").then((m) => ({ default: m.TeamsPage })));
const ProviderHealthPage = lazy(() => import("./features/providers/ProviderHealthPage").then((m) => ({ default: m.ProviderHealthPage })));
const ModelRegistryPage = lazy(() => import("./features/modelregistry/ModelRegistryPage").then((m) => ({ default: m.ModelRegistryPage })));
const ProviderKeysPage = lazy(() => import("./features/providerkeys/ProviderKeysPage").then((m) => ({ default: m.ProviderKeysPage })));
const ExperimentsPage = lazy(() => import("./features/experiments/ExperimentsPage").then((m) => ({ default: m.ExperimentsPage })));
const ConversationsPage = lazy(() => import("./features/conversations/ConversationsPage").then((m) => ({ default: m.ConversationsPage })));
const DatasetsPage = lazy(() => import("./features/evaluation/DatasetsPage").then((m) => ({ default: m.DatasetsPage })));
const EvaluatorsPage = lazy(() => import("./features/evaluation/EvaluatorsPage").then((m) => ({ default: m.EvaluatorsPage })));
const EvalRunsPage = lazy(() => import("./features/evaluation/EvalRunsPage").then((m) => ({ default: m.EvalRunsPage })));
const PolicyConfigPage = lazy(() => import("./features/policy/PolicyConfigPage").then((m) => ({ default: m.PolicyConfigPage })));
const AuditLogPage = lazy(() => import("./features/audit/AuditLogPage").then((m) => ({ default: m.AuditLogPage })));
const BillingPage = lazy(() => import("./features/billing/BillingPage").then((m) => ({ default: m.BillingPage })));
const PlaygroundPage = lazy(() => import("./features/playground/PlaygroundPage").then((m) => ({ default: m.PlaygroundPage })));
const McpServersPage = lazy(() => import("./features/mcp/McpServersPage").then((m) => ({ default: m.McpServersPage })));

export function App() {
  const { token, isRestoring } = useAuth();

  if (isRestoring) {
    return (
      <div className="page-loading">
        <div className="loader" />
      </div>
    );
  }

  return (
    <>
      <Toaster
        position="top-center"
        toastOptions={{
          style: {
            background: "var(--surface)",
            border: "1px solid var(--line)",
            color: "var(--text)",
            fontFamily: "var(--font-sans)",
          },
        }}
      />
      {!token ? (
        <Suspense fallback={<LoadingState label="Loading…" />}>
        <Routes>
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/sso-callback" element={<SSOCallbackPage />} />
          <Route path="/accept-invite" element={<AcceptInvitePage />} />
          <Route path="*" element={<LoginPage />} />
        </Routes>
        </Suspense>
      ) : (
        <>
        <OnboardingModal />
        <Routes>
          <Route path="/" element={<AdminLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="logs" element={<LogsPage />} />
            <Route path="logs/:id" element={<RequestTracePage />} />
            <Route path="api-keys" element={<ApiKeysPage />} />
            <Route path="provider-keys" element={<ProviderKeysPage />} />
            <Route path="model-registry" element={<ModelRegistryPage />} />
            <Route path="provider-health" element={<ProviderHealthPage />} />
            <Route path="mcp-servers" element={<McpServersPage />} />
            <Route path="experiments" element={<ExperimentsPage />} />
            <Route path="datasets" element={<DatasetsPage />} />
            <Route path="evaluators" element={<EvaluatorsPage />} />
            <Route path="eval-runs" element={<EvalRunsPage />} />
            <Route path="policy" element={<PolicyConfigPage />} />
            <Route path="teams" element={<TeamsPage />} />
            <Route path="users-roles" element={<UsersRolesPage />} />
            <Route path="organization-settings" element={<OrganizationSettingsPage />} />
            <Route path="billing" element={<BillingPage />} />
            <Route path="audit" element={<AuditLogPage />} />
            <Route path="playground" element={<PlaygroundPage />} />
            <Route path="conversations" element={<ConversationsPage />} />
            <Route path="conversations/:id" element={<ConversationsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </>
      )}
    </>
  );
}
