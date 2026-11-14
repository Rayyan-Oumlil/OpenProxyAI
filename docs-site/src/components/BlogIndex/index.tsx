import React, {useMemo, useRef, useState} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import type {Props as BlogListProps} from '@theme/BlogListPage';

import SearchIcon from '@site/src/components/SearchIcon';
import {useFocusShortcut} from '@site/src/hooks/useFocusShortcut';
import PostCard, {type Post} from './PostCard';
import {BLOG_PATH, TOPICS} from './topics';
import styles from './styles.module.css';

const HERO_COUNT = 2;
const GRID_PAGE_SIZE = 12;

interface BlogIndexProps {
  items: BlogListProps['items'];
  /** Permalink of the topic being shown, or undefined for all posts. */
  activeTopic?: string;
}

function matches(post: Post, query: string): boolean {
  const haystack = [
    post.title,
    post.description,
    ...post.tags.map((tag) => tag.label),
  ]
    .join(' ')
    .toLowerCase();
  return query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => haystack.includes(word));
}

export default function BlogIndex({
  items,
  activeTopic,
}: BlogIndexProps): React.JSX.Element {
  const [query, setQuery] = useState('');
  const [gridLimit, setGridLimit] = useState(GRID_PAGE_SIZE);
  const searchRef = useRef<HTMLInputElement>(null);
  useFocusShortcut(searchRef);

  const posts = useMemo(() => items.map(({content}) => content.metadata), [items]);
  const searching = query.trim() !== '';
  const found = useMemo(
    () => (searching ? posts.filter((post) => matches(post, query)) : posts),
    [posts, query, searching],
  );

  // Search results are one flat grid; the two large cards are for browsing.
  const heroes = searching ? [] : found.slice(0, HERO_COUNT);
  const rest = searching ? found : found.slice(HERO_COUNT);
  const grid = searching ? rest : rest.slice(0, gridLimit);
  const remaining = rest.length - grid.length;

  const topicLabel = (post: Post): string | undefined =>
    (post.tags.find((tag) => tag.permalink === activeTopic) ?? post.tags[0])
      ?.label;

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>Blog</h1>
        <div className={styles.tools}>
          <label className={styles.search}>
            <SearchIcon className={styles.searchIcon} />
            <span className={styles.srOnly}>Search posts</span>
            <input
              ref={searchRef}
              type="search"
              className={styles.searchInput}
              placeholder="Search…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              autoComplete="off"
              spellCheck={false}
            />
            <kbd className={styles.kbd} aria-hidden="true">
              Ctrl K
            </kbd>
          </label>
        </div>
      </header>

      <nav aria-label="Filter posts by topic">
        <ul className={styles.pills}>
          {[{label: 'All', permalink: BLOG_PATH}, ...TOPICS].map((topic) => {
            const active =
              topic.permalink === (activeTopic ?? BLOG_PATH);
            return (
              <li key={topic.permalink}>
                <Link
                  to={topic.permalink}
                  className={clsx(styles.pill, active && styles.pillActive)}
                  aria-current={active ? 'page' : undefined}>
                  {topic.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <p className={styles.srOnly} role="status">
        {searching ? `${found.length} posts match “${query.trim()}”.` : ''}
      </p>

      {heroes.length > 0 && (
        <ul className={clsx(styles.grid, styles.heroGrid)}>
          {heroes.map((post) => (
            <PostCard
              key={post.permalink}
              post={post}
              topic={topicLabel(post)}
              hero
            />
          ))}
        </ul>
      )}

      {grid.length > 0 && (
        <ul className={styles.grid}>
          {grid.map((post) => (
            <PostCard key={post.permalink} post={post} topic={topicLabel(post)} />
          ))}
        </ul>
      )}

      {searching && found.length === 0 && (
        <div className={styles.empty}>
          <p>No posts match “{query.trim()}”.</p>
          <button
            type="button"
            className={styles.button}
            onClick={() => {
              setQuery('');
              searchRef.current?.focus();
            }}>
            Clear search
          </button>
        </div>
      )}

      {remaining > 0 && (
        <div className={styles.more}>
          <button
            type="button"
            className={styles.button}
            onClick={() => setGridLimit((limit) => limit + GRID_PAGE_SIZE)}>
            Show {Math.min(remaining, GRID_PAGE_SIZE)} more posts
          </button>
        </div>
      )}
    </main>
  );
}
