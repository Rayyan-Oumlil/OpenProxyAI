import React from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import type {Props as BlogListProps} from '@theme/BlogListPage';

import PostCover from '@site/src/components/PostCover';
import {formatPostDate} from './topics';
import styles from './styles.module.css';

export type Post = BlogListProps['items'][number]['content']['metadata'];

interface PostCardProps {
  post: Post;
  /** Label shown on the cover; the topic being browsed, or the post's first one. */
  topic?: string;
  hero?: boolean;
}

export default function PostCard({
  post,
  topic,
  hero = false,
}: PostCardProps): React.JSX.Element {
  return (
    <li className={clsx(styles.card, hero && styles.cardHero)}>
      <PostCover
        seed={post.permalink}
        title={post.title}
        topic={topic}
        shape={hero ? 'hero' : 'card'}
        className={styles.cover}
      />
      <h2 className={styles.cardTitle}>
        {/* The only link in the card; its ::after stretches over the cover too. */}
        <Link to={post.permalink} className={styles.cardLink}>
          {post.title}
        </Link>
      </h2>
      <p className={styles.meta}>
        <time dateTime={post.date}>{formatPostDate(post.date)}</time>
        {post.readingTime !== undefined && (
          <span>{Math.max(1, Math.ceil(post.readingTime))} min read</span>
        )}
      </p>
    </li>
  );
}
