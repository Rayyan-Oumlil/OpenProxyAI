import { useState } from "react";
import type { FormEvent } from "react";

import { apiClient } from "../../api/client";
import type { ApiKeyCreatedResponse } from "../../api/types";

type StepCreateKeyProps = {
  token: string;
  onKeyCreated: (response: ApiKeyCreatedResponse) => void;
  onSkip: () => void;
};

export function StepCreateKey({ token, onKeyCreated, onSkip }: StepCreateKeyProps) {
  const [keyName, setKeyName] = useState("My First Key");
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = keyName.trim();
    if (!trimmed) return;

    setIsCreating(true);
    setError(null);

    try {
      const created = await apiClient.post<ApiKeyCreatedResponse>(
        "/api/v1/api-keys",
        { name: trimmed, permissions: ["proxy:llm"], expires_at: null },
        token
      );
      onKeyCreated(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create API key.");
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="onboarding-step">
      <div className="onboarding-step-indicator">
        <span className="onboarding-dot onboarding-dot--active" />
        <span className="onboarding-dot" />
        <span className="onboarding-dot" />
      </div>

      <h2 className="onboarding-title">Create your first API key</h2>
      <p className="onboarding-description">
        An API key lets you route LLM requests through OpenProxy. Give it a name
        so you can identify it later.
      </p>

      <form onSubmit={handleSubmit} className="onboarding-form">
        <label htmlFor="onboarding-key-name" className="onboarding-label">
          Key name
        </label>
        <input
          id="onboarding-key-name"
          type="text"
          value={keyName}
          onChange={(e) => setKeyName(e.target.value)}
          placeholder="e.g. My First Key"
          required
          autoFocus
        />

        {error ? <p className="form-error">{error}</p> : null}

        <button type="submit" disabled={isCreating || !keyName.trim()}>
          {isCreating ? "Creating..." : "Create Key"}
        </button>
      </form>

      <button type="button" className="onboarding-skip" onClick={onSkip}>
        Skip onboarding
      </button>
    </div>
  );
}
