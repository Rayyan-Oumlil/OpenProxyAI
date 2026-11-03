import { ChevronRight } from "lucide-react";
import { Fragment, useId, type KeyboardEvent, type ReactNode } from "react";

import { cn } from "../../lib/utils";

export interface Column<T> {
  key: string;
  header: string;
  cell: (row: T) => ReactNode;
  align?: "left" | "right";
  /** IDs, models and numbers read better in the mono face with tabular figures. */
  mono?: boolean;
  /** Keeps a long value (a timestamp) on one line. */
  nowrap?: boolean;
}

export interface TableMessage {
  title: string;
  detail: string;
}

export interface TableError extends TableMessage {
  onRetry?: () => void;
}

interface DataTableProps<T> {
  /** Names the table for screen readers; also shown to everyone as the caption when `showCaption` is set. */
  caption: string;
  columns: Column<T>[];
  rows: T[] | undefined;
  getRowId: (row: T) => string;
  isLoading?: boolean;
  error?: TableError | null;
  empty: TableMessage;
  skeletonRows?: number;
  density?: "comfortable" | "compact";
  onRowClick?: (row: T) => void;
  /** Rows for which this returns false are not clickable or focusable. Defaults to every row. */
  isRowInteractive?: (row: T) => boolean;
  /** When set, the row with this id renders `renderExpanded(row)` underneath it. */
  expandedId?: string | null;
  renderExpanded?: (row: T) => ReactNode;
  /** Names a row for its expand button ("Show details for github"); falls back to a generic label. */
  getRowLabel?: (row: T) => string;
  footer?: ReactNode;
}

function Skeleton({ columns, rows }: { columns: number; rows: number }) {
  return (
    <>
      {Array.from({ length: rows }, (_, r) => (
        <tr key={r} className="dt__skeleton-row" aria-hidden="true">
          {Array.from({ length: columns }, (_, c) => (
            <td key={c}>
              <span className="dt__skeleton" style={{ width: `${55 + ((r * 7 + c * 13) % 40)}%` }} />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

export function DataTable<T>({
  caption,
  columns,
  rows,
  getRowId,
  isLoading = false,
  error = null,
  empty,
  skeletonRows = 6,
  density = "comfortable",
  onRowClick,
  isRowInteractive,
  expandedId = null,
  renderExpanded,
  getRowLabel,
  footer,
}: DataTableProps<T>) {
  const tableId = useId();
  const expandable = Boolean(renderExpanded && onRowClick);
  const columnCount = columns.length + (expandable ? 1 : 0);
  if (error) {
    return (
      <div className="dt dt--message" role="alert">
        <p className="dt__message-title">{error.title}</p>
        <p className="dt__message-detail">{error.detail}</p>
        {error.onRetry ? (
          <button type="button" className="btn-outline" onClick={error.onRetry}>
            Try again
          </button>
        ) : null}
      </div>
    );
  }

  const showEmpty = !isLoading && (rows?.length ?? 0) === 0;
  if (showEmpty) {
    return (
      <div className="dt dt--message" aria-live="polite">
        <p className="dt__message-title">{empty.title}</p>
        <p className="dt__message-detail">{empty.detail}</p>
      </div>
    );
  }

  function onKeyDown(event: KeyboardEvent<HTMLTableRowElement>, row: T) {
    if (event.target !== event.currentTarget) return; // let buttons and links inside the row handle their own keys
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onRowClick?.(row);
    }
  }

  return (
    <div className={cn("dt", density === "compact" && "dt--compact")}>
      <div className="dt__scroll" tabIndex={0} role="region" aria-label={caption}>
        <table aria-busy={isLoading}>
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr>
              {expandable ? (
                <th scope="col" className="dt__toggle-col">
                  <span className="sr-only">Details</span>
                </th>
              ) : null}
              {columns.map((column) => (
                <th key={column.key} scope="col" className={cn(column.align === "right" && "dt__right")}>
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <Skeleton columns={columnCount} rows={skeletonRows} />
            ) : (
              (rows ?? []).map((row) => {
                const id = getRowId(row);
                const expanded = expandedId === id;
                const interactive = Boolean(onRowClick) && (isRowInteractive?.(row) ?? true);
                return (
                  <Fragment key={id}>
                    <tr
                      className={cn(interactive && "dt__row--clickable", expanded && "dt__row--open")}
                      tabIndex={interactive && !expandable ? 0 : undefined}
                      onClick={interactive ? () => onRowClick?.(row) : undefined}
                      onKeyDown={interactive && !expandable ? (event) => onKeyDown(event, row) : undefined}
                    >
                      {expandable ? (
                        <td className="dt__toggle-col">
                          {interactive ? (
                            <button
                              type="button"
                              className="dt__toggle"
                              aria-expanded={expanded}
                              aria-controls={expanded ? `${tableId}-detail-${id}` : undefined}
                              aria-label={`${expanded ? "Hide" : "Show"} details${getRowLabel ? ` for ${getRowLabel(row)}` : ""}`}
                              onClick={(event) => {
                                event.stopPropagation(); // the row's own click would toggle a second time
                                onRowClick?.(row);
                              }}
                            >
                              <ChevronRight size={16} aria-hidden="true" />
                            </button>
                          ) : null}
                        </td>
                      ) : null}
                      {columns.map((column) => (
                        <td
                          key={column.key}
                          className={cn(column.align === "right" && "dt__right", column.mono && "dt__mono", column.nowrap && "dt__nowrap")}
                        >
                          {column.cell(row)}
                        </td>
                      ))}
                    </tr>
                    {expanded && renderExpanded ? (
                      <tr className="dt__detail" id={`${tableId}-detail-${id}`}>
                        <td colSpan={columnCount}>{renderExpanded(row)}</td>
                      </tr>
                    ) : null}
                  </Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      {footer ? <div className="dt__footer">{footer}</div> : null}
    </div>
  );
}
