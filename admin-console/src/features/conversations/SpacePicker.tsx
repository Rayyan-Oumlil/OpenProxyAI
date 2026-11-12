import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../../api/client";
import type { Space } from "../../api/conversationTypes";
import { useAuth } from "../../state/AuthContext";

export const SPACES = "/api/v1/spaces";

export function useSpaces(enabled = true) {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["spaces"],
    queryFn: () => apiClient.get<Space[]>(SPACES, token!),
    enabled: Boolean(token) && enabled,
  });
}

/** Pick the space a conversation is filed in. A space is a folder: filing a conversation never changes who can read it. */
export function SpacePicker({
  id,
  value,
  onChange,
  label = "Space",
  emptyLabel = "No space",
}: {
  id: string;
  value: string;
  onChange: (spaceId: string) => void;
  label?: string;
  emptyLabel?: string;
}) {
  const spaces = useSpaces();
  return (
    <label className="inline-control" htmlFor={id}>
      {label}
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{emptyLabel}</option>
        {(spaces.data ?? []).map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
            {s.team_id ? " (team)" : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
