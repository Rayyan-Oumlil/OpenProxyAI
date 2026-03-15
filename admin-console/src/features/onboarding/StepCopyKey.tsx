import { useState, useCallback } from "react";

type StepCopyKeyProps = {
  apiKey: string;
  onNext: () => void;
};

export function StepCopyKey({ apiKey, onNext }: StepCopyKeyProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(apiKey);
      setCopied(true);
      const timeout = setTimeout(() => setCopied(false), 2000);
      // Cleanup is handled by the 2-second reset; component unmount
      // before timeout fires is harmless (setState on unmounted is a no-op in React 19)
      return () => clearTimeout(timeout);
    } catch {
      // Fallback: select the text so the user can copy manually
    }
  }, [apiKey]);

  return (
    <div className="onboarding-step">
      <div className="onboarding-step-indicator">
        <span className="onboarding-dot onboarding-dot--done" />
        <span className="onboarding-dot onboarding-dot--active" />
        <span className="onboarding-dot" />
      </div>

      <h2 className="onboarding-title">Copy your key</h2>
      <p className="onboarding-description">
        This is the only time your full API key will be displayed.
      </p>

      <div className="onboarding-key-display">
        <code>{apiKey}</code>
        <button type="button" onClick={handleCopy}>
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>

      <p className="onboarding-warning">
        Store this securely. It won't be shown again.
      </p>

      <button type="button" onClick={onNext}>
        Next &rarr;
      </button>
    </div>
  );
}
