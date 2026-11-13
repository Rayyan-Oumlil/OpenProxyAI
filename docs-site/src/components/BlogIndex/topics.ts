export interface Topic {
  label: string;
  permalink: string;
}

export const BLOG_PATH = '/blog';
export const FEED_PATH = `pathname://${BLOG_PATH}/rss.xml`;

/** Mirrors blog/tags.yml. Add a topic there and here together. */
export const TOPICS: readonly Topic[] = [
  {label: 'Architecture', permalink: `${BLOG_PATH}/tags/architecture`},
  {label: 'Security', permalink: `${BLOG_PATH}/tags/security`},
  {label: 'Engineering', permalink: `${BLOG_PATH}/tags/engineering`},
  {label: 'Product', permalink: `${BLOG_PATH}/tags/product`},
];

const DATE_FORMAT = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  // Fixed zone so the server and the browser print the same day.
  timeZone: 'UTC',
});

export function formatPostDate(iso: string): string {
  return DATE_FORMAT.format(new Date(iso));
}
