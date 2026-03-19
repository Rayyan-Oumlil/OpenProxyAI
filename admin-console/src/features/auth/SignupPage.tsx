import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../../state/AuthContext";

export function SignupPage() {
  const { signup, isAuthenticating, error } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [orgName, setOrgName] = useState("");

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await signup({ email, password, name, org_name: orgName });
  };

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <p className="eyebrow">OpenProxy</p>
        <h1>Create your account</h1>
        <p className="muted">Set up your AI gateway in minutes. No credit card required.</p>

        <form onSubmit={onSubmit} className="auth-form">
          <label htmlFor="name">Your name</label>
          <input
            id="name"
            name="name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Jane Smith"
            required
          />

          <label htmlFor="org-name">Organization name</label>
          <input
            id="org-name"
            name="org_name"
            type="text"
            value={orgName}
            onChange={(e) => setOrgName(e.target.value)}
            placeholder="Acme Corp"
            required
          />

          <label htmlFor="email">Work email</label>
          <input
            id="email"
            name="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            required
          />

          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="At least 8 characters"
            minLength={8}
            required
          />

          {error ? <p className="form-error">{error}</p> : null}

          <button type="submit" disabled={isAuthenticating}>
            {isAuthenticating ? "Creating account..." : "Create account"}
          </button>
        </form>

        <p className="auth-footer">
          Already have an account?{" "}
          <Link to="/login">Sign in</Link>
        </p>
      </section>
    </main>
  );
}
