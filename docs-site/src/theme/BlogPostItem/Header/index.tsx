import React from 'react';
import Link from '@docusaurus/Link';
import {useBlogPost} from '@docusaurus/plugin-content-blog/client';

import PostCover from '@site/src/components/PostCover';
import {BLOG_PATH, formatPostDate} from '@site/src/components/BlogIndex/topics';
import styles from './styles.module.css';

export default function BlogPostItemHeader(): React.JSX.Element {
  const {metadata} = useBlogPost();
  const {title, date, readingTime, permalink, tags, description} = metadata;
  return (
    <header className={styles.header}>
      <Link to={BLOG_PATH} className={styles.back}>
        <span aria-hidden="true">&larr;</span> All posts
      </Link>
      <p className={styles.meta}>
        <time dateTime={date}>{formatPostDate(date)}</time>
        {readingTime !== undefined && (
          <span>{Math.max(1, Math.ceil(readingTime))} min read</span>
        )}
      </p>
      <h1 className={styles.title}>{title}</h1>
      {description && <p className={styles.subtitle}>{description}</p>}
      <PostCover
        seed={permalink}
        topic={tags[0]?.label}
        shape="banner"
        className={styles.cover}
      />
    </header>
  );
}
