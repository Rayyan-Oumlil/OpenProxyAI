// Pre-renders every route to static HTML after `vite build` and `vite build --ssr`,
// writes per-page <head> tags and sitemap.xml.
import fs from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const SITE = 'https://openproxyai.com'
const dist = path.resolve('dist')
const ssr = path.resolve('dist-ssr')

const pages = [
  {
    route: '/',
    title: 'OpenProxyAI | Open-source LLM gateway for enterprise AI',
    description:
      'OpenProxyAI is an open-source, self-hosted LLM gateway. One OpenAI-compatible endpoint for every provider, with policy enforcement, budgets, routing by data class, and an audit trail.',
  },
  {
    route: '/product',
    title: 'Product | OpenProxyAI',
    description:
      'See how OpenProxyAI routes, governs and logs every LLM call: policies, budgets and rate limits, caching, failover, MCP gateway, evals and an admin console.',
  },
  {
    route: '/security',
    title: 'Security and compliance | OpenProxyAI',
    description:
      'Self-hosted in your VPC with row-level security, an append-only audit trail, SSO and SCIM, data residency and compliance templates for HIPAA, PCI and FedRAMP-aligned setups.',
  },
  {
    route: '/providers',
    title: 'Providers and models | OpenProxyAI',
    description:
      'Use OpenAI, Anthropic, Azure, Mistral, local models and your own endpoints through one gateway, with failover and routing rules that respect your data classes.',
  },
  {
    route: '/pricing',
    title: 'Pricing | OpenProxyAI',
    description:
      'OpenProxyAI is open source under Apache-2.0 and free to self-host. See what is included and how to get help running it in production.',
  },
]

const esc = (s) => s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;')

const jsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Organization',
      name: 'OpenProxyAI',
      url: SITE,
      logo: `${SITE}/og-image.png`,
      sameAs: ['https://github.com/Rayyan-Oumlil/OpenProxyAI', 'https://docs.openproxyai.com'],
    },
    {
      '@type': 'SoftwareApplication',
      name: 'OpenProxyAI',
      applicationCategory: 'DeveloperApplication',
      operatingSystem: 'Linux, macOS, Windows (Docker)',
      license: 'https://www.apache.org/licenses/LICENSE-2.0',
      url: SITE,
      description:
        'Open-source, self-hosted LLM gateway with policy enforcement, budgets, routing and audit logging.',
      offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
    },
  ],
}

const template = fs.readFileSync(path.join(dist, 'index.html'), 'utf8')
const { render } = await import(pathToFileURL(path.join(ssr, 'entry-server.js')).href)

function head(p) {
  const url = SITE + (p.route === '/' ? '' : p.route)
  const t = esc(p.title)
  const d = esc(p.description)
  return [
    `<title>${t}</title>`,
    `<meta name="description" content="${d}" />`,
    `<link rel="canonical" href="${url}" />`,
    `<meta property="og:type" content="website" />`,
    `<meta property="og:site_name" content="OpenProxyAI" />`,
    `<meta property="og:title" content="${t}" />`,
    `<meta property="og:description" content="${d}" />`,
    `<meta property="og:url" content="${url}" />`,
    `<meta property="og:image" content="${SITE}/og-image.png" />`,
    `<meta property="og:image:width" content="1200" />`,
    `<meta property="og:image:height" content="630" />`,
    `<meta name="twitter:card" content="summary_large_image" />`,
    `<meta name="twitter:title" content="${t}" />`,
    `<meta name="twitter:description" content="${d}" />`,
    `<meta name="twitter:image" content="${SITE}/og-image.png" />`,
    p.route === '/' ? `<script type="application/ld+json">${JSON.stringify(jsonLd)}</script>` : '',
  ].join('\n    ')
}

// Remove the placeholder head tags that index.html carries for the dev server.
const stripped = template
  .replace(/<title>[\s\S]*?<\/title>\s*/, '')
  .replace(/<meta (name="(description|twitter:[a-z]+)"|property="og:[a-z:]+")[^>]*>\s*/g, '')

for (const p of pages) {
  const html = stripped
    .replace('</head>', () => `    ${head(p)}\n  </head>`)
    .replace('<div id="root"></div>', () => `<div id="root">${render(p.route)}</div>`)
  const out = p.route === '/' ? path.join(dist, 'index.html') : path.join(dist, p.route, 'index.html')
  fs.mkdirSync(path.dirname(out), { recursive: true })
  fs.writeFileSync(out, html)
  console.log('prerendered', p.route, `${(html.length / 1024).toFixed(0)} KB`)
}

const today = new Date().toISOString().slice(0, 10)
const urls = pages
  .map((p) => `  <url><loc>${SITE}${p.route === '/' ? '/' : p.route}</loc><lastmod>${today}</lastmod></url>`)
  .join('\n')
fs.writeFileSync(
  path.join(dist, 'sitemap.xml'),
  `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`,
)
fs.rmSync(ssr, { recursive: true, force: true })
