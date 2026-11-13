import React from 'react';
import clsx from 'clsx';
import {
  PageMetadata,
  HtmlClassNameProvider,
  ThemeClassNames,
} from '@docusaurus/theme-common';
import Layout from '@theme/Layout';
import SearchMetadata from '@theme/SearchMetadata';
import type {Props} from '@theme/BlogTagsPostsPage';

import BlogIndex from '@site/src/components/BlogIndex';

export default function BlogTagsPostsPage({
  tag,
  items,
}: Props): React.JSX.Element {
  return (
    <HtmlClassNameProvider
      className={clsx(
        ThemeClassNames.wrapper.blogPages,
        ThemeClassNames.page.blogTagPostListPage,
      )}>
      <PageMetadata
        title={`${tag.label} posts`}
        description={tag.description}
      />
      <SearchMetadata tag="blog_tags_posts" />
      <Layout>
        <BlogIndex items={items} activeTopic={tag.permalink} />
      </Layout>
    </HtmlClassNameProvider>
  );
}
