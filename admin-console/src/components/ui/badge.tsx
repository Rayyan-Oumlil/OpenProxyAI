import { cn } from "../../lib/utils";

type BadgeVariant = "default" | "success" | "error" | "warning" | "policy" | "muted";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const variantClasses: Record<BadgeVariant, string> = {
  default: "bg-[rgba(15,23,42,0.06)] text-foreground",
  success: "bg-[rgba(20,184,166,0.1)] text-[#0f766e]",
  error: "bg-[rgba(239,68,68,0.1)] text-[#b91c1c]",
  warning: "bg-[rgba(245,158,11,0.1)] text-[#92400e]",
  policy: "bg-[rgba(14,165,233,0.1)] text-[#0369a1]",
  muted: "bg-[rgba(100,116,139,0.08)] text-muted",
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
