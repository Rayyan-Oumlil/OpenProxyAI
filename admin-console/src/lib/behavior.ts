export type Level = "low" | "medium" | "high";
export type Length = "short" | "medium" | "long";

/** Provider-neutral behaviour settings. An absent key means "not set". */
export type BehaviorSettings = {
  creativity?: Level;
  reasoning_depth?: Level;
  max_response_length?: Length;
  citations?: boolean;
};

export type BehaviorCeiling = Omit<BehaviorSettings, "citations">;

export const LEVELS: { value: Level; label: string }[] = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];

export const LENGTHS: { value: Length; label: string }[] = [
  { value: "short", label: "Short (about 256 tokens)" },
  { value: "medium", label: "Medium (about 1,024 tokens)" },
  { value: "long", label: "Long (about 4,096 tokens)" },
];

/** What a setting becomes for a provider, in words. The mapping itself lives on the server (services/behavior.py). */
export const BEHAVIOR_HELP = {
  creativity: "Becomes the model's temperature: low 0.2, medium 0.7, high 1.0.",
  reasoning_depth: "Becomes reasoning effort, only for models that accept it. For other models it is ignored and the request log says so.",
  max_response_length: "Becomes the answer's token limit.",
  citations: "Adds an instruction to name sources and to say when there is none.",
} as const;

/** A copy of `settings` with `key` set, or removed when `value` is empty. */
export function withSetting<T extends BehaviorSettings>(settings: T, key: keyof BehaviorSettings, value: string | boolean | undefined): T {
  const next: Record<string, unknown> = { ...settings };
  if (value === undefined || value === "") delete next[key];
  else next[key] = value;
  return next as T;
}
