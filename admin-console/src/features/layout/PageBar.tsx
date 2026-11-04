import { Search } from "lucide-react";
import { Fragment, useMemo } from "react";
import { Link } from "react-router-dom";

import type { Crumb } from "./breadcrumbs";

interface PageBarProps {
  crumbs: Crumb[];
  onOpenSearch: () => void;
}

/** Where you are (breadcrumbs, from the same data as the sidebar) and the way to jump elsewhere (the palette). */
export function PageBar({ crumbs, onOpenSearch }: PageBarProps) {
  const shortcut = useMemo(() => (/Mac|iPhone|iPad/i.test(navigator.userAgent) ? "⌘K" : "Ctrl K"), []);
  return (
    <div className="pagebar">
      {crumbs.length > 0 ? (
        <nav aria-label="Breadcrumb">
          <ol className="crumbs">
            {crumbs.map((crumb, index) => {
              const last = index === crumbs.length - 1;
              return (
                <Fragment key={`${crumb.label}-${index}`}>
                  <li className="crumbs__item" aria-current={last ? "page" : undefined}>
                    {crumb.to && !last ? <Link to={crumb.to}>{crumb.label}</Link> : crumb.label}
                  </li>
                  {last ? null : (
                    <li className="crumbs__sep" aria-hidden="true">
                      /
                    </li>
                  )}
                </Fragment>
              );
            })}
          </ol>
        </nav>
      ) : (
        <span />
      )}
      <button type="button" className="btn-outline pagebar__search" onClick={onOpenSearch} aria-keyshortcuts="Control+K Meta+K">
        <Search size={14} aria-hidden="true" />
        <span className="pagebar__search-text">Search</span>
        <kbd className="pagebar__kbd">
          {shortcut}
        </kbd>
      </button>
    </div>
  );
}
