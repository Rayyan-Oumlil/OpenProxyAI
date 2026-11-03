import { formatCost, formatPercent } from "../../lib/utils";
import type { Burndown } from "../../features/dashboard/metrics";

const W = 640;
const H = 190;
const M = { top: 12, right: 12, bottom: 22, left: 12 };

function summary(b: Burndown): string {
  const spent = `Spent ${formatCost(b.spentToDate)}`;
  const budget = b.budget != null && b.budgetUsed != null ? ` of ${formatCost(b.budget)} budget (${formatPercent(b.budgetUsed, 0)})` : "";
  const projected = b.projected != null ? `, projected ${formatCost(b.projected)} by month end` : "";
  const over = b.budget != null && b.projected != null && b.projected > b.budget ? ". On track to exceed the budget." : "";
  return `${spent}${budget}${projected}${over}`;
}

/** Cumulative spend this month against the monthly budget, with a straight-line projection to month end. */
export function BudgetBurndown({ burndown: b }: { burndown: Burndown }) {
  const days = b.spent.length;
  const top = Math.max(b.budget ?? 0, b.projected ?? 0, b.spentToDate, 0.000001) * 1.1;
  const x = (day: number) => M.left + ((day - 1) / Math.max(b.daysInMonth - 1, 1)) * (W - M.left - M.right);
  const y = (value: number) => M.top + (1 - value / top) * (H - M.top - M.bottom);

  const spentPoints = b.spent.map((value, i) => `${x(i + 1).toFixed(1)},${y(value).toFixed(1)}`).join(" ");
  const overBudget = b.budgetUsed != null && b.budgetUsed > 1;
  const caption = summary(b);

  return (
    <figure className="burndown">
      <figcaption className="burndown__caption">{caption}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Budget burn-down. ${caption}`} className="burndown__svg">
        <line x1={M.left} x2={W - M.right} y1={y(0)} y2={y(0)} className="burndown__axis" />
        {b.budget != null ? (
          <line x1={M.left} x2={W - M.right} y1={y(b.budget)} y2={y(b.budget)} className="burndown__budget" />
        ) : null}
        {b.projected != null && days < b.daysInMonth ? (
          <line x1={x(days)} y1={y(b.spentToDate)} x2={x(b.daysInMonth)} y2={y(b.projected)} className="burndown__projection" />
        ) : null}
        <polyline points={spentPoints} className={overBudget ? "burndown__spent burndown__spent--over" : "burndown__spent"} fill="none" />
        <text x={M.left} y={H - 6} className="burndown__tick">Day 1</text>
        <text x={W - M.right} y={H - 6} textAnchor="end" className="burndown__tick">Day {b.daysInMonth}</text>
      </svg>
      <p className="burndown__legend" aria-hidden="true">
        <span className="burndown__key burndown__key--spent">Spent</span>
        {b.budget != null ? <span className="burndown__key burndown__key--budget">Budget</span> : null}
        <span className="burndown__key burndown__key--projection">Projection</span>
      </p>
    </figure>
  );
}
