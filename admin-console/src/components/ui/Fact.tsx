import type { ReactNode } from "react";

/** One label and value in a `<dl className="trace-facts">` list: the request trace and the policy preview use it. */
export function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="trace-fact">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
