/** The three products under Product. One list feeds the menu, the footer, the command palette and the cards. */
export const SUB_PRODUCTS = [
  {
    slug: 'web-browser-control',
    href: '/product/web-browser-control',
    name: 'Web Browser Control',
    menu: 'A browser extension that monitors AI use in real time.',
    body: 'A browser extension for employee desktops. It monitors prompts and AI answers in real time, reports personal data sent to unauthorized AI, and redacts and reports sensitive uploads.',
  },
  {
    slug: 'central-ai-proxy',
    href: '/product/central-ai-proxy',
    name: 'Central AI Proxy',
    menu: 'The only gateway to generative AI, inside and out.',
    body: 'The gateway everyone in the company goes through to use generative AI. It reaches OpenAI, Claude, Perplexity and others, and connects safely to local MCP servers and local models.',
  },
  {
    slug: 'central-dlp-protection',
    href: '/product/central-dlp-protection',
    name: 'Central DLP Protection',
    menu: 'Ingest sensitive documents, match every prompt.',
    body: 'Two paths: ingest your documents, scanned ones included, into one vector database, then search every outgoing prompt against it and report a positive match.',
  },
] as const;

export type SubProductSlug = (typeof SUB_PRODUCTS)[number]['slug'];
