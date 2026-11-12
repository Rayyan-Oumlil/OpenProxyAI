import { useId } from "react";

import { BEHAVIOR_HELP, LENGTHS, LEVELS, withSetting, type BehaviorSettings } from "../lib/behavior";

type Props = {
  value: BehaviorSettings;
  onChange: (next: BehaviorSettings) => void;
  /** Citations are a default or a request, never a ceiling. */
  withCitations?: boolean;
  disabled?: boolean;
  /** What the empty option says, e.g. "No default" or "No ceiling". */
  noneLabel: string;
};

/** The four behaviour settings as selects. Used for the org's defaults and ceiling, and for a playground request. */
export function BehaviorControls({ value, onChange, withCitations = true, disabled = false, noneLabel }: Props) {
  const id = useId();
  const select = (key: "creativity" | "reasoning_depth" | "max_response_length", label: string, options: { value: string; label: string }[]) => (
    <label className="inline-control" htmlFor={`${id}-${key}`}>
      {label}
      <select
        id={`${id}-${key}`}
        value={value[key] ?? ""}
        disabled={disabled}
        aria-describedby={`${id}-${key}-help`}
        onChange={(e) => onChange(withSetting(value, key, e.target.value))}
      >
        <option value="">{noneLabel}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <span id={`${id}-${key}-help`} className="muted" style={{ fontSize: "0.8rem" }}>
        {BEHAVIOR_HELP[key]}
      </span>
    </label>
  );

  return (
    <div className="stack-form">
      {select("creativity", "Creativity", LEVELS)}
      {select("reasoning_depth", "Reasoning depth", LEVELS)}
      {select("max_response_length", "Response length", LENGTHS)}
      {withCitations ? (
        <label className="flex items-start gap-2 text-sm" htmlFor={`${id}-citations`}>
          <input
            id={`${id}-citations`}
            type="checkbox"
            checked={value.citations ?? false}
            disabled={disabled}
            aria-describedby={`${id}-citations-help`}
            onChange={(e) => onChange(withSetting(value, "citations", e.target.checked ? true : undefined))}
            style={{ marginTop: 3 }}
          />
          <span>
            Ask for citations
            <span id={`${id}-citations-help`} className="muted block" style={{ fontSize: "0.8rem" }}>
              {BEHAVIOR_HELP.citations}
            </span>
          </span>
        </label>
      ) : null}
    </div>
  );
}
