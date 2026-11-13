import React from 'react';
import clsx from 'clsx';

import CoverArt from './CoverArt';
import {designFor, round} from './design';
import styles from './styles.module.css';

interface PostCoverProps {
  /** Anything stable per post; the permalink works. */
  seed: string;
  /** Left out on the post page, where the heading sits right above the cover. */
  title?: string;
  topic?: string;
  shape?: 'hero' | 'card' | 'banner';
  className?: string;
}

const SHORT_TITLE = 34;
const MEDIUM_TITLE = 58;

function sizeClass(title: string): string {
  if (title.length <= SHORT_TITLE) {
    return styles.titleLarge;
  }
  return title.length <= MEDIUM_TITLE ? styles.titleMedium : styles.titleSmall;
}

/**
 * A drawn cover so every post has a picture without any image file.
 * Purely decorative: hidden from assistive tech, the real title is next to it.
 */
export default function PostCover({
  seed,
  title,
  topic,
  shape = 'card',
  className,
}: PostCoverProps): React.JSX.Element {
  const design = designFor(seed);
  const glow = {
    '--cover-glow-x': `${round(design.glowX)}%`,
    '--cover-glow-y': `${round(design.glowY)}%`,
  } as React.CSSProperties;
  return (
    <div
      aria-hidden="true"
      className={clsx(
        styles.cover,
        styles[shape],
        design.align === 'left' ? styles.left : styles.center,
        className,
      )}
      style={glow}>
      <CoverArt design={design} />
      {(topic || title) && (
        <div className={styles.text}>
          {topic && <span className={styles.chip}>{topic}</span>}
          {title && (
            <span className={clsx(styles.title, sizeClass(title))}>{title}</span>
          )}
        </div>
      )}
    </div>
  );
}
