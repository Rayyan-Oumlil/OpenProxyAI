import { NavLink, Link } from 'react-router';
import { NAV } from '../site/nav';
import { GITHUB_URL, DOCS_URL } from '../site/links';

export default function Navigation() {
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-bg/80 backdrop-blur">
      <nav aria-label="Main" className="mx-auto flex h-14 max-w-page items-center gap-6 px-4 sm:px-6">
        <Link to="/" className="font-mono text-step-0 font-semibold tracking-tight">OpenProxyAI</Link>
        <ul className="hidden items-center gap-5 md:flex">
          {NAV.map(item => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                className={({ isActive }) => `text-step--1 ${isActive ? 'text-ink' : 'text-ink-dim hover:text-ink'}`}
              >
                {item.label}
              </NavLink>
            </li>
          ))}
          <li><a href={DOCS_URL} className="text-step--1 text-ink-dim hover:text-ink">Docs ↗</a></li>
        </ul>
        <a
          href={GITHUB_URL}
          className="ml-auto rounded-md bg-signal px-3 py-1.5 text-step--1 font-semibold text-bg hover:brightness-110"
        >
          View on GitHub
        </a>
      </nav>
    </header>
  );
}
