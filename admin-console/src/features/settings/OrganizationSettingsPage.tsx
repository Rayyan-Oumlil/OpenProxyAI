import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { apiClient } from "../../api/client";
import type { OrganizationResponse } from "../../api/types";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { LoadingState } from "../../components/LoadingState";
import { useAuth } from "../../state/AuthContext";

export function OrganizationSettingsPage() {
  const { token, user } = useAuth();
  const queryClient = useQueryClient();

  const [name, setName] = useState("");
  const [budgetMonthly, setBudgetMonthly] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [dataRegion, setDataRegion] = useState<string>("us");
  const [settingsJson, setSettingsJson] = useState("{}");
  const [formError, setFormError] = useState<string | null>(null);
  const [showDataRegionWarning, setShowDataRegionWarning] = useState(false);

  const orgQuery = useQuery({
    queryKey: ["organization", "current", token],
    queryFn: () => apiClient.get<OrganizationResponse>("/api/v1/organizations/current", token!),
    enabled: Boolean(token),
  });

  useEffect(() => {
    if (!orgQuery.data) {
      return;
    }
    setName(orgQuery.data.name);
    setBudgetMonthly(orgQuery.data.budget_monthly_usd ?? "");
    setIsActive(orgQuery.data.is_active);
    setDataRegion(orgQuery.data.data_region ?? "us");
    setSettingsJson(JSON.stringify(orgQuery.data.settings ?? {}, null, 2));
  }, [orgQuery.data]);

  const updateMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiClient.patch<OrganizationResponse>("/api/v1/organizations/current", payload, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["organization", "current", token] });
      setFormError(null);
    },
  });

  const canManageSettings = user?.role === "admin";

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canManageSettings) {
      return;
    }

    let parsedSettings: Record<string, unknown>;
    try {
      parsedSettings = JSON.parse(settingsJson) as Record<string, unknown>;
    } catch {
      setFormError("Settings must be valid JSON.");
      return;
    }

    try {
      await updateMutation.mutateAsync({
        name,
        budget_monthly_usd: budgetMonthly === "" ? null : Number(budgetMonthly),
        is_active: isActive,
        data_region: dataRegion,
        settings: parsedSettings,
      });
      setFormError(null);
      setShowDataRegionWarning(false);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to save settings.");
    }
  };

  if (orgQuery.isLoading) {
    return <LoadingState label="Loading organization settings..." />;
  }

  if (orgQuery.isError) {
    return (
      <ErrorState
        title="Unable to load organization"
        detail={orgQuery.error instanceof Error ? orgQuery.error.message : "Unknown error"}
      />
    );
  }

  if (!orgQuery.data) {
    return <EmptyState title="Organization not found" detail="No organization data returned." />;
  }

  return (
    <section className="page-wrap">
      <header className="page-header">
        <p className="eyebrow">Workspace Configuration</p>
        <h1>Organization Settings</h1>
      </header>

      {!canManageSettings ? (
        <EmptyState title="Read-only access" detail="Only admin users can modify organization settings." />
      ) : null}

      <section className="surface-panel">
        <form className="stack-form" onSubmit={onSubmit}>
          <label htmlFor="org-name">Organization name</label>
          <input
            id="org-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            disabled={!canManageSettings || updateMutation.isPending}
          />

          <label>Plan</label>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
            <span>{orgQuery.data.plan}</span>
            <Link to="/billing">Manage in Billing →</Link>
          </div>

          <label htmlFor="org-budget">Monthly budget (USD)</label>
          <input
            id="org-budget"
            type="number"
            min="0"
            step="0.01"
            value={budgetMonthly}
            onChange={(event) => setBudgetMonthly(event.target.value)}
            disabled={!canManageSettings || updateMutation.isPending}
          />

          <label htmlFor="org-active" className="check-row">
            <input
              id="org-active"
              type="checkbox"
              checked={isActive}
              onChange={(event) => setIsActive(event.target.checked)}
              disabled={!canManageSettings || updateMutation.isPending}
            />
            Organization active
          </label>

          <label htmlFor="org-data-region">Data Region</label>
          <select
            id="org-data-region"
            value={dataRegion}
            onChange={(e) => {
              const newVal = e.target.value;
              const prev = orgQuery.data?.data_region ?? "us";
              setDataRegion(newVal);
              setShowDataRegionWarning(newVal !== prev);
            }}
            disabled={!canManageSettings || updateMutation.isPending}
            style={{ maxWidth: "12rem" }}
          >
            <option value="us">US</option>
            <option value="eu">EU</option>
            <option value="ap">Asia-Pacific</option>
          </select>
          {showDataRegionWarning ? (
            <p
              className="form-warning"
              style={{
                marginTop: "0.25rem",
                padding: "0.5rem",
                background: "rgba(234, 179, 8, 0.15)",
                borderRadius: "4px",
                fontSize: "0.875rem",
              }}
            >
              Changing your data region means only provider keys tagged for the new region (or
              &quot;global&quot;) will be used. Ensure you have keys configured for the target
              region.
            </p>
          ) : null}

          <label htmlFor="org-settings-json">Settings JSON</label>
          <textarea
            id="org-settings-json"
            className="settings-json"
            value={settingsJson}
            onChange={(event) => setSettingsJson(event.target.value)}
            disabled={!canManageSettings || updateMutation.isPending}
          />

          {formError ? <p className="form-error">{formError}</p> : null}

          <button type="submit" disabled={!canManageSettings || updateMutation.isPending}>
            {updateMutation.isPending ? "Saving..." : "Save Settings"}
          </button>
        </form>
      </section>
    </section>
  );
}

