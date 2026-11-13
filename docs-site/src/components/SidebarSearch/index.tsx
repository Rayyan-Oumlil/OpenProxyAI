import React, {useMemo, useRef, useState} from 'react';
import Link from '@docusaurus/Link';
import type {PropSidebar, PropSidebarItem} from '@docusaurus/plugin-content-docs';

import SearchIcon from '@site/src/components/SearchIcon';
import {useFocusShortcut} from '@site/src/hooks/useFocusShortcut';
import styles from './styles.module.css';

interface PageLink {
  label: string;
  href: string;
  section?: string;
}

function collectPages(items: readonly PropSidebarItem[], section?: string): PageLink[] {
  return items.flatMap((item): PageLink[] => {
    if (item.type === 'link') {
      return [{label: item.label, href: item.href, section}];
    }
    if (item.type === 'category') {
      const own = item.href ? [{label: item.label, href: item.href, section}] : [];
      return [...own, ...collectPages(item.items, item.label)];
    }
    return [];
  });
}

interface SidebarSearchProps {
  sidebar: PropSidebar;
  /** The normal sidebar menu, shown whenever the box is empty. */
  children: React.ReactNode;
}

/**
 * Finds pages by title within the current section's sidebar.
 * It is a title filter, not full-text search: the site has no search index.
 */
export default function SidebarSearch({
  sidebar,
  children,
}: SidebarSearchProps): React.JSX.Element {
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  useFocusShortcut(inputRef);

  const pages = useMemo(() => collectPages(sidebar), [sidebar]);
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const searching = words.length > 0;
  const results = searching
    ? pages.filter((page) => {
        const haystack = `${page.label} ${page.section ?? ''}`.toLowerCase();
        return words.every((word) => haystack.includes(word));
      })
    : [];

  return (
    <>
      <div className={styles.box}>
        <label className={styles.field}>
          <SearchIcon className={styles.icon} />
          <span className={styles.srOnly}>Search page titles</span>
          <input
            ref={inputRef}
            type="search"
            className={styles.input}
            placeholder="Search pages…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Escape') {
                setQuery('');
              }
            }}
            autoComplete="off"
            spellCheck={false}
          />
          <kbd className={styles.kbd} aria-hidden="true">
            Ctrl K
          </kbd>
        </label>
      </div>
      {searching ? (
        <nav className={`menu thin-scrollbar ${styles.results}`} aria-label="Matching pages">
          <p className={styles.count} role="status">
            {results.length === 0
              ? 'No page title matches.'
              : `${results.length} ${results.length === 1 ? 'page' : 'pages'}`}
          </p>
          <ul className="menu__list">
            {results.map((page) => (
              <li key={page.href} className="menu__list-item">
                <Link className="menu__link" to={page.href} onClick={() => setQuery('')}>
                  {page.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      ) : (
        children
      )}
    </>
  );
}
