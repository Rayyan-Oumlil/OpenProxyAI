import { Link } from 'react-router';
import { GITHUB_URL, LINKEDIN_URL, DOCS_URL } from '../site/links';

export default function Footer() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-page flex-col gap-4 px-4 py-10 text-step--1 text-ink-dim sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <p>
          Designed &amp; built by{' '}
          <a href={LINKEDIN_URL} className="text-ink hover:text-signal">Rayyan Oumlil</a>
        </p>
        <ul className="flex gap-5">
          <li><Link to="/engineering" className="hover:text-ink">How it's built</Link></li>
          <li><a href={GITHUB_URL} className="hover:text-ink">GitHub</a></li>
          <li><a href={DOCS_URL} className="hover:text-ink">Docs</a></li>
        </ul>
      </div>
    </footer>
  );
}
