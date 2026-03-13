import { useState } from "react";
import type { FormEvent } from "react";

import { useAuth } from "../../state/AuthContext";

export function LoginPage() {
  const { login, isAuthenticating, error } = useAuth();
  const [email, setEmail] = useState("admin@openproxy.ai");
  const [password, setPassword] = useState("password123");

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await login({ email, password });
  };

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <p className="eyebrow">OpenProxy Admin</p>
        <h1>Operate Your AI Gateway</h1>
        <p className="muted">Track spend, inspect requests, and control API keys in one place.</p>

        <form onSubmit={onSubmit} className="auth-form">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            name="email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />

          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />

          {error ? <p className="form-error">{error}</p> : null}

          <button type="submit" disabled={isAuthenticating}>
            {isAuthenticating ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}

