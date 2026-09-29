import type { MetaDescriptor } from 'react-router';

const SITE = 'https://openproxyai.com';

export function pageMeta({ title, description, path }: { title: string; description: string; path: string }): MetaDescriptor[] {
  const url = `${SITE}${path === '/' ? '' : path}`;
  const slug = path === '/' ? 'home' : path.slice(1);
  const image = `${SITE}/og/${slug}.png`;
  return [
    { title },
    { name: 'description', content: description },
    { property: 'og:type', content: 'website' },
    { property: 'og:site_name', content: 'OpenProxyAI' },
    { property: 'og:title', content: title },
    { property: 'og:description', content: description },
    { property: 'og:url', content: url },
    { property: 'og:image', content: image },
    { property: 'og:image:width', content: '1200' },
    { property: 'og:image:height', content: '630' },
    { name: 'twitter:card', content: 'summary_large_image' },
    { name: 'twitter:image', content: image },
    { tagName: 'link', rel: 'canonical', href: url },
  ];
}
