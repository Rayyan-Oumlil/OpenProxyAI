import { useEffect, useRef } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiClient } from "../../api/client";
import type { AnalyticsResponse, OrganizationResponse } from "../../api/types";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { LoadingState } from "../../components/LoadingState";
import { useAuth } from "../../state/AuthContext";

type PlanCard = {
  name: string;
  price: string;
  description: string;
  cta: string;
  targetPlan?: "starter" | "growth" | "metered";
};

const PLAN_CARDS: PlanCard[] = [
  {
    name: "Free",
    price: "$0/mo",
    description: "Baseline access for evaluation and low-volume usage.",
    cta: "Current baseline",
  },
  {
    name: "Starter",
    price: "$2,500/mo",
    description: "For growing teams that need policy and spend controls.",
    cta: "Upgrade to Starter",
    targetPlan: "starter",
  },
  {
    name: "Growth",
    price: "$7,500/mo",
    description: "For larger teams with higher throughput and governance needs.",
    cta: "Upgrade to Growth",
    targetPlan: "growth",
  },
  {
    name: "Metered",
    price: "Base + usage",
    description: "Usage-based token billing via Stripe metered pricing with an included monthly allowance.",
    cta: "Upgrade to Metered",
    targetPlan: "metered",
  },
  {
    name: "Enterprise",
    price: "Contact sales",
    description: "Custom contracts, security reviews, and dedicated support.",
    cta: "Contact Sales",
  },
];

export function BillingPage() {
  const { token, user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const handledSuccess = useRef(false);
  const handledCanceled = useRef(false);

  const orgQuery = useQuery({
    queryKey: ["organization", "current", token],
    queryFn: () => apiClient.get<OrganizationResponse>("/api/v1/organizations/current", token!),
    enabled: Boolean(token),
  });

  const analyticsQuery = useQuery({
    queryKey: ["analytics", "overview", "billing", token],
    queryFn: () =>
      apiClient.get<AnalyticsResponse>("/api/v1/analytics/overview?period_days=30", token!),
    enabled: Boolean(token) && orgQuery.data?.plan?.toLowerCase() === "metered",
  });

  const checkoutMutation = useMutation({
    mutationFn: (plan: "starter" | "growth" | "metered") => apiClient.createCheckoutSession(plan, token!),
    onSuccess: (data) => {
      window.location.href = data.checkout_url;
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Failed to create checkout session");
    },
  });

  const portalMutation = useMutation({
    mutationFn: () => apiClient.createPortalSession(token!),
    onSuccess: (data) => {
      window.location.href = data.portal_url;
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Failed to open billing portal");
    },
  });

  const success = searchParams.get("success") === "1";
  const canceled = searchParams.get("canceled") === "1";

  useEffect(() => {
    if (!canceled || handledCanceled.current) return;
    handledCanceled.current = true;
    toast.message("Checkout canceled. No charges were made.");
    const next = new URLSearchParams(searchParams);
    next.delete("canceled");
    setSearchParams(next, { replace: true });
  }, [canceled, searchParams, setSearchParams]);

  useEffect(() => {
    if (!success || !orgQuery.data || handledSuccess.current) return;
    handledSuccess.current = true;
    const originalPlan = orgQuery.data.plan;
    toast.message("Payment processing...");
    let elapsedMs = 0;
    const interval = window.setInterval(async () => {
      elapsedMs += 3000;
      const refreshed = await orgQuery.refetch();
      const updatedPlan = refreshed.data?.plan;
      if (updatedPlan && updatedPlan !== originalPlan) {
        toast.success(`Plan updated to ${updatedPlan}.`);
        window.clearInterval(interval);
        const next = new URLSearchParams(searchParams);
        next.delete("success");
        setSearchParams(next, { replace: true });
      } else if (elapsedMs >= 30000) {
        toast.message("Payment is still processing. Please refresh in a moment.");
        window.clearInterval(interval);
      }
    }, 3000);
    return () => window.clearInterval(interval);
  }, [success, orgQuery, orgQuery.data, searchParams, setSearchParams]);

  if (orgQuery.isLoading) {
    return <LoadingState label="Loading billing details..." />;
  }
  if (orgQuery.isError) {
    return (
      <ErrorState
        title="Unable to load billing details"
        detail={orgQuery.error instanceof Error ? orgQuery.error.message : "Unknown error"}
      />
    );
  }
  if (!orgQuery.data) {
    return <EmptyState title="Billing unavailable" detail="Organization was not found." />;
  }

  const canManage = user?.role === "admin";
  const currentPlan = orgQuery.data.plan.toLowerCase();
  const subStatus = orgQuery.data.stripe_subscription_status ?? "none";
  const hasStripeCustomer = Boolean(orgQuery.data.stripe_customer_id);

  return (
    <section className="page-wrap">
      <header className="page-header">
        <p className="eyebrow">Billing</p>
        <h1>Plan & Subscription</h1>
      </header>

      <section className="surface-panel" style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
        <div>
          <p style={{ color: "var(--muted)", marginBottom: "0.25rem" }}>Current plan</p>
          <h2 style={{ fontSize: "1.2rem", fontWeight: 700 }}>{orgQuery.data.plan}</h2>
        </div>
        <div>
          <p style={{ color: "var(--muted)", marginBottom: "0.25rem" }}>Subscription status</p>
          <span
            style={{
              border: "1px solid var(--line)",
              borderRadius: "999px",
              padding: "0.25rem 0.65rem",
              textTransform: "lowercase",
              fontSize: "0.85rem",
            }}
          >
            {subStatus}
          </span>
        </div>
        <div>
          <button
            type="button"
            onClick={() => portalMutation.mutate()}
            disabled={!canManage || !hasStripeCustomer || portalMutation.isPending}
          >
            {portalMutation.isPending ? "Opening..." : "Manage Billing"}
          </button>
        </div>
      </section>

      {currentPlan === "metered" &&
        typeof orgQuery.data.included_tokens_monthly === "number" &&
        orgQuery.data.included_tokens_monthly > 0 && (
          <section className="surface-panel" style={{ marginTop: "1rem" }}>
            <h2 style={{ fontSize: "1.05rem", fontWeight: 700, marginBottom: "0.5rem" }}>
              Usage vs included allowance
            </h2>
            <p style={{ color: "var(--muted)", fontSize: "0.88rem", marginBottom: "0.75rem" }}>
              Compared to your monthly included tokens (from{" "}
              <code style={{ fontSize: "0.85em" }}>GET /api/v1/analytics/overview</code> last 30 days).
            </p>
            {analyticsQuery.isLoading ? (
              <p style={{ color: "var(--muted)" }}>Loading usage…</p>
            ) : analyticsQuery.isError ? (
              <p style={{ color: "var(--danger, #c00)" }}>Could not load analytics overview.</p>
            ) : (
              (() => {
                const included = orgQuery.data.included_tokens_monthly!;
                const used = analyticsQuery.data?.overview.total_tokens ?? 0;
                const pct = Math.min(100, Math.round((used / included) * 1000) / 10);
                const basis = analyticsQuery.data?.overview.forecast_basis_days ?? 0;
                const projectedMonthTokens =
                  basis > 0 ? Math.round((used / basis) * 30) : null;
                const overageTokens =
                  projectedMonthTokens !== null ? Math.max(0, projectedMonthTokens - included) : null;
                return (
                  <div style={{ display: "grid", gap: "0.65rem" }}>
                    <div>
                      <span style={{ color: "var(--muted)" }}>Tokens (30d window)</span>
                      <div style={{ fontWeight: 700 }}>
                        {used.toLocaleString()} / {included.toLocaleString()} included ({pct}%)
                      </div>
                    </div>
                    <div
                      style={{
                        height: 8,
                        borderRadius: 4,
                        background: "var(--line, #ddd)",
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          width: `${pct}%`,
                          height: "100%",
                          background: pct > 90 ? "var(--danger, #c62828)" : "var(--accent, #2563eb)",
                        }}
                      />
                    </div>
                    {projectedMonthTokens !== null && (
                      <p style={{ color: "var(--muted)", fontSize: "0.88rem" }}>
                        Projected month-end tokens (linear):{" "}
                        <strong>{projectedMonthTokens.toLocaleString()}</strong>
                        {overageTokens !== null && overageTokens > 0 && (
                          <>
                            {" "}
                            — estimated overage vs included:{" "}
                            <strong>{overageTokens.toLocaleString()}</strong> tokens
                          </>
                        )}
                      </p>
                    )}
                  </div>
                );
              })()
            )}
          </section>
        )}

      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: "0.9rem",
        }}
      >
        {PLAN_CARDS.map((plan) => {
          const isCurrent = plan.targetPlan
            ? currentPlan === plan.targetPlan
            : currentPlan === plan.name.toLowerCase();
          const canUpgrade = canManage && plan.targetPlan && !isCurrent;
          return (
            <article key={plan.name} className="surface-panel" style={{ display: "grid", gap: "0.6rem" }}>
              <div>
                <h3 style={{ fontWeight: 700 }}>{plan.name}</h3>
                <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>{plan.price}</p>
              </div>
              <p style={{ color: "var(--muted)", fontSize: "0.88rem" }}>{plan.description}</p>
              {plan.targetPlan ? (
                <button
                  type="button"
                  disabled={!canUpgrade || checkoutMutation.isPending}
                  onClick={() => checkoutMutation.mutate(plan.targetPlan!)}
                >
                  {isCurrent
                    ? "Current plan"
                    : checkoutMutation.isPending
                    ? "Redirecting..."
                    : plan.cta}
                </button>
              ) : (
                <button type="button" disabled>
                  {isCurrent ? "Current plan" : plan.cta}
                </button>
              )}
            </article>
          );
        })}
      </section>

      <section className="surface-panel">
        <p style={{ color: "var(--muted)" }}>
          Manual organization settings no longer controls billing plans. Use this page for upgrades and
          subscription management.
        </p>
        <p style={{ marginTop: "0.5rem" }}>
          <Link to="/organization-settings">Back to organization settings</Link>
        </p>
      </section>
    </section>
  );
}
