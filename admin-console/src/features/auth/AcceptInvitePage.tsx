import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useAuth } from "../../state/AuthContext";

export function AcceptInvitePage() {
  const [searchParams] = useSearchParams();
  const { acceptInvite, isAuthenticating, error } = useAuth();
  const navigate = useNavigate();

  const token = searchParams.get("token") ?? "";
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");

  if (!token) {
    return (
      <main className="auth-shell">
        <section className="auth-card">
          <p className="eyebrow">OpenProxy Admin</p>
          <h1>Invalid invite link</h1>
          <p className="muted">This invite link is missing a token. Request a new invite from your admin.</p>
          <button type="button" onClick={() => navigate("/", { replace: true })}>
            Back to sign in
          </button>
        </section>
      </main>
    );
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    await acceptInvite({ token, name: name.trim(), password });
    navigate("/", { replace: true });
  }

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <p className="eyebrow">OpenProxy Admin</p>
        <h1>You've been invited</h1>
        <p className="muted">Create your account to join your team's AI gateway.</p>

        <form onSubmit={onSubmit} className="auth-form">
          <label htmlFor="invite-name">Your name</label>
          <input
            id="invite-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Jane Smith"
            required
            minLength={1}
            autoFocus
          />

          <label htmlFor="invite-password">Choose a password</label>
          <input
            id="invite-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="At least 8 characters"
            required
            minLength={8}
          />

          {error ? <p className="form-error">{error}</p> : null}

          <button type="submit" disabled={isAuthenticating}>
            {isAuthenticating ? "Creating account…" : "Accept invite & sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
