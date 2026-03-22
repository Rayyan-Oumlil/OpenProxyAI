import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../../state/AuthContext";

/**
 * Handles redirect from SSO callback (C03: one-time code flow).
 * Reads `code` from URL, exchanges for tokens, then redirects to dashboard.
 */
export function SSOCallbackPage() {
  const [searchParams] = useSearchParams();
  const { applySsoCode, error, isAuthenticating } = useAuth();
  const navigate = useNavigate();
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (done) return;
    const code = searchParams.get("code");
    if (!code) {
      setDone(true);
      navigate("/", { replace: true });
      return;
    }
    void applySsoCode(code)
      .then(() => {
        setDone(true);
        navigate("/", { replace: true });
      })
      .catch(() => {
        setDone(true);
      });
  }, [searchParams, applySsoCode, navigate, done]);

  if (isAuthenticating && !done) {
    return (
      <main className="auth-shell">
        <section className="auth-card">
          <p className="eyebrow">OpenProxy Admin</p>
          <h1>Completing sign-in…</h1>
          <div className="loader" style={{ margin: "1rem auto" }} />
        </section>
      </main>
    );
  }

  if (error) {
    return (
      <main className="auth-shell">
        <section className="auth-card">
          <p className="eyebrow">OpenProxy Admin</p>
          <h1>Sign-in failed</h1>
          <p className="form-error">{error}</p>
          <button type="button" onClick={() => navigate("/", { replace: true })}>
            Back to sign in
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <p className="eyebrow">OpenProxy Admin</p>
        <h1>Redirecting…</h1>
        <div className="loader" style={{ margin: "1rem auto" }} />
      </section>
    </main>
  );
}
