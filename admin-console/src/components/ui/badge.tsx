import { cn } from "../../lib/utils";

type BadgeVariant = "default" | "success" | "error" | "warning" | "policy" | "muted";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const variantClasses: Record<BadgeVariant, string> = {
  default: "bg-[var(--bg-hover)] text-foreground",
  success: "bg-[color-mix(in_srgb,var(--ok)_14%,transparent)] text-[var(--ok)]",
  error: "bg-[color-mix(in_srgb,var(--err)_14%,transparent)] text-[var(--err)]",
  warning: "bg-[color-mix(in_srgb,var(--warn)_14%,transparent)] text-[var(--warn)]",
  // The accent on its own tint is about 4:1 in the light theme; mixing in the text colour clears the 4.5:1 that WCAG AA asks of small text.
  policy: "bg-[color-mix(in_srgb,var(--accent)_14%,transparent)] text-[color-mix(in_srgb,var(--accent)_70%,var(--text))]",
  muted: "bg-[var(--bg-sunken)] text-muted",
};

export function Badge({ variant = "default", className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium",
        variantClasses[variant],
        className
      )}
      {...props}
    />
  );
}
