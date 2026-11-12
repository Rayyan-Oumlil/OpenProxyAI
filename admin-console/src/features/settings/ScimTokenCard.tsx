import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "../../api/client";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../../components/ui/dialog";
import { useConfirm } from "../../components/ui/ConfirmDialog";
import { Fact } from "../../components/ui/Fact";
import { formatDateTime } from "../../lib/utils";
import { useAuth } from "../../state/AuthContext";

interface ScimTokenStatus {
  configured: boolean;
  token_prefix: string | null;
  created_at: string | null;
  last_used_at: string | null;
  scim_base_url: string;
}

interface ScimTokenCreated extends ScimTokenStatus {
  token: string;
  rotated: boolean;
}

const STATUS_PATH = "/api/v1/scim/token";

/** Create, rotate and revoke the org's SCIM token. The token is shown once, in a dialog, and never stored by the console. */
export function ScimTokenCard() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [created, setCreated] = useState<ScimTokenCreated | null>(null);
  const [copied, setCopied] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const statusQuery = useQuery({
    queryKey: ["scim-token", token],
    queryFn: () => apiClient.get<ScimTokenStatus>(STATUS_PATH, token!),
    enabled: Boolean(token),
    retry: false,
  });

  const createMutation = useMutation({
    mutationFn: () => apiClient.post<ScimTokenCreated>(STATUS_PATH, {}, token!),
    onSuccess: (result) => {
      setActionError(null);
      setCreated(result);
      queryClient.invalidateQueries({ queryKey: ["scim-token", token] });
    },
    onError: (error) => setActionError(error instanceof Error ? error.message : "Could not create the token."),
  });

  const revokeMutation = useMutation({
    mutationFn: () => apiClient.del<void>(STATUS_PATH, token!),
    onSuccess: () => {
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ["scim-token", token] });
    },
    onError: (error) => setActionError(error instanceof Error ? error.message : "Could not revoke the token."),
  });

  const status = statusQuery.data;
  const configured = Boolean(status?.configured);
  const busy = createMutation.isPending || revokeMutation.isPending;

  // The buttons use aria-disabled while a request is in flight, not `disabled`: a disabled button drops keyboard focus,
  // and the dialogs that open next would then have nowhere to return it.
  async function createOrRotate() {
    if (busy || statusQuery.isLoading) return;
    if (configured) {
      const ok = await confirm({
        title: "Rotate the SCIM token?",
        description: "The current token stops working immediately. Put the new token into your identity provider straight away, or provisioning will fail.",
        confirmLabel: "Rotate token",
        destructive: true,
      });
      if (!ok) return;
    }
    createMutation.mutate();
  }

  async function revoke() {
    if (busy) return;
    const ok = await confirm({
      title: "Revoke the SCIM token?",
      description: "Your identity provider can no longer create, update or deactivate users until you create a new token. Existing users are not changed.",
      confirmLabel: "Revoke token",
      destructive: true,
    });
    if (ok) revokeMutation.mutate();
  }

  async function copy(value: string) {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <section className="surface-panel" aria-labelledby="scim-heading">
      <h2 id="scim-heading">User provisioning (SCIM)</h2>
      <p>
        Let Okta or Microsoft Entra ID create, update and deactivate users automatically. New users are created as viewers; roles are
        always set here, never by the identity provider.
      </p>

      {statusQuery.isLoading ? <p role="status">Loading SCIM status...</p> : null}
      {statusQuery.isError ? (
        <p className="form-error" role="alert">
          {statusQuery.error instanceof Error ? statusQuery.error.message : "Unable to load SCIM status."}
        </p>
      ) : null}

      {status ? (
        <dl className="trace-facts">
          <Fact label="Status">{configured ? "Token active" : "No token"}</Fact>
          {configured ? (
            <>
              <Fact label="Token">
                <code>{status.token_prefix}…</code>
              </Fact>
              <Fact label="Created">{status.created_at ? formatDateTime(status.created_at) : "—"}</Fact>
              <Fact label="Last used">{status.last_used_at ? formatDateTime(status.last_used_at) : "Never"}</Fact>
            </>
          ) : null}
          <Fact label="SCIM base URL">
            <code>{status.scim_base_url}</code>
          </Fact>
        </dl>
      ) : null}

      {actionError ? (
        <p className="form-error" role="alert">
          {actionError}
        </p>
      ) : null}

      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
        <button type="button" onClick={createOrRotate} aria-disabled={busy || statusQuery.isLoading}>
          {configured ? "Rotate token" : "Create token"}
        </button>
        {configured ? (
          <button type="button" className="btn-danger" onClick={revoke} aria-disabled={busy}>
            Revoke token
          </button>
        ) : null}
      </div>

      {created ? (
        <Dialog
          open
          onOpenChange={(open) => {
            if (!open) {
              setCreated(null);
              setCopied(false);
            }
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{created.rotated ? "SCIM token rotated" : "SCIM token created"}</DialogTitle>
              <DialogDescription>Copy it now. It is shown only once and cannot be recovered; if you lose it, rotate it.</DialogDescription>
            </DialogHeader>
            <p>
              <strong>Token</strong>
            </p>
            <code style={{ display: "block", wordBreak: "break-all" }} data-testid="scim-token-value">
              {created.token}
            </code>
            <p>
              <strong>SCIM base URL</strong>
            </p>
            <code style={{ display: "block", wordBreak: "break-all" }}>{created.scim_base_url}</code>
            <DialogFooter>
              <button type="button" onClick={() => copy(created.token)}>
                {copied ? "Copied" : "Copy token"}
              </button>
              <button type="button" onClick={() => setCreated(null)}>
                Done
              </button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      ) : null}
    </section>
  );
}
