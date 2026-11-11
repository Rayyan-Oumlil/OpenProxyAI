import type { AdaptiveStatus, ExperimentResponse, VariantMetrics } from "../../api/types";

export const DELTA_CHOICES: { value: number; label: string; detail: string }[] = [
  { value: 0.01, label: "Careful (1%)", detail: "Default. Rarely names a winner between variants that are really equal; takes longer." },
  { value: 0.05, label: "Standard (5%)", detail: "Faster, but with repeated checking it names a false winner far more often when variants are equal." },
  { value: 0.1, label: "Quick (10%)", detail: "Fastest and the most likely to be wrong. Fine for a rough look." },
];

export function isAdaptive(e: Pick<ExperimentResponse, "mode">): boolean {
  return e.mode === "adaptive";
}

/** The model of the variant that won, if the test has stopped with a winner. */
export function winnerOf(e: ExperimentResponse): ExperimentResponse["variants"][number] | undefined {
  return e.winner_variant_id ? e.variants.find((v) => v.id === e.winner_variant_id) : undefined;
}

type Sample = { model: string; n: number };

/** Ratings still needed before anything is decided: the variant furthest from the minimum sets the pace. */
export function ratingsStillNeeded(adaptive: AdaptiveStatus): number {
  const counts = Object.values(adaptive.samples);
  if (counts.length === 0) return adaptive.min_samples_per_variant;
  return Math.max(0, ...counts.map((n) => adaptive.min_samples_per_variant - n));
}

export function samplesByModel(experiment: ExperimentResponse, adaptive: AdaptiveStatus): Sample[] {
  return experiment.variants.map((v) => ({ model: v.model, n: v.id ? (adaptive.samples[v.id] ?? 0) : 0 }));
}

/** 0.9731 -> "97%"; under a tenth of a percent is shown as "<1%" and over 99.9 as ">99%", never a misleading 0 or 100. */
export function chanceLabel(p: number | null | undefined): string {
  if (p == null) return "—";
  if (p > 0 && p < 0.01) return "<1%";
  if (p < 1 && p > 0.99) return ">99%";
  return `${Math.round(p * 100)}%`;
}

/** A stable key for a result row: two variants can run the same model, so the model alone is not unique. */
export function resultKey(v: VariantMetrics, index: number): string {
  return v.variant_id ?? `${v.model}#${index}`;
}

/** True when the edit form changes the variants, as opposed to the other settings. Sending unchanged variants would replace them. */
export function variantsChanged(
  before: Array<{ model: string; traffic_weight: number }>,
  after: Array<{ model: string; traffic_weight: number }>,
): boolean {
  if (before.length !== after.length) return true;
  return before.some((b, i) => b.model !== after[i].model || b.traffic_weight !== after[i].traffic_weight);
}
