import { useEffect, useState } from "react";

import { apiClient } from "../../api/client";
import type { ApiKeyCreatedResponse, ApiKeyResponse } from "../../api/types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog";
import { useAuth } from "../../state/AuthContext";

import { StepCopyKey } from "./StepCopyKey";
import { StepCreateKey } from "./StepCreateKey";
import { StepStartUsing } from "./StepStartUsing";

const STORAGE_KEY = "openproxy_onboarding_dismissed";

type OnboardingStep = 1 | 2 | 3;

function isDismissed(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function markDismissed(): void {
  try {
    localStorage.setItem(STORAGE_KEY, "1");
  } catch {
    // localStorage unavailable — silently ignore
  }
}

export function OnboardingModal() {
  const { token } = useAuth();

  const [isOpen, setIsOpen] = useState(false);
  const [step, setStep] = useState<OnboardingStep>(1);
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [isChecking, setIsChecking] = useState(true);

  // On mount: decide whether to show the modal
  useEffect(() => {
    if (!token) {
      setIsChecking(false);
      return;
    }

    if (isDismissed()) {
      setIsChecking(false);
      return;
    }

    let cancelled = false;

    async function checkExistingKeys() {
      try {
        const keys = await apiClient.get<ApiKeyResponse[]>("/api/v1/api-keys", token!);
        if (!cancelled && keys.length === 0) {
          setIsOpen(true);
        }
      } catch {
        // If the request fails, don't show the modal — fail safe
      } finally {
        if (!cancelled) {
          setIsChecking(false);
        }
      }
    }

    checkExistingKeys();

    return () => {
      cancelled = true;
    };
  }, [token]);

  const handleKeyCreated = (response: ApiKeyCreatedResponse) => {
    setCreatedKey(response.key);
    setStep(2);
  };

  const handleDismiss = () => {
    markDismissed();
    setIsOpen(false);
  };

  const handleSkip = () => {
    markDismissed();
    setIsOpen(false);
  };

  const handleNextToStep3 = () => {
    setStep(3);
  };

  // Don't render anything while checking or if not open
  if (isChecking || !isOpen || !token) {
    return null;
  }

  return (
    <Dialog open={isOpen} onOpenChange={() => { /* Prevent closing via overlay/escape */ }}>
      <DialogContent
        onPointerDownOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
        onInteractOutside={(e) => e.preventDefault()}
        className="max-w-md onboarding-dialog"
      >
        <DialogHeader>
          <DialogTitle className="sr-only">Onboarding</DialogTitle>
          <DialogDescription className="sr-only">
            Set up your first API key to start using OpenProxy.
          </DialogDescription>
        </DialogHeader>

        {step === 1 ? (
          <StepCreateKey
            token={token}
            onKeyCreated={handleKeyCreated}
            onSkip={handleSkip}
          />
        ) : null}

        {step === 2 && createdKey ? (
          <StepCopyKey apiKey={createdKey} onNext={handleNextToStep3} />
        ) : null}

        {step === 3 && createdKey ? (
          <StepStartUsing apiKey={createdKey} onDismiss={handleDismiss} />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
