import type { ReactNode } from "react";

type PageHeaderProps = {
  title: string;
  description?: string;
  /** Buttons or filters aligned to the right on wide screens, stacked below the title on narrow ones. */
  actions?: ReactNode;
};

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <header className="page-head">
      <div className="page-head__text">
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="page-head__actions">{actions}</div> : null}
    </header>
  );
}
