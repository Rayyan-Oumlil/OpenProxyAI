import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const config: Config = {
  title: 'OpenProxyAI Docs',
  tagline: 'The control plane for enterprise AI',
  favicon: 'img/favicon.ico',

  future: {
    v4: true,
  },

  url: 'https://docs.openproxy.ai',
  baseUrl: '/',

  organizationName: 'openproxyai',
  projectName: 'openproxyai-docs',

  onBrokenLinks: 'warn',
  onBrokenAnchors: 'warn',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          routeBasePath: '/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
        sitemap: {
          lastmod: 'date',
          changefreq: 'weekly',
          priority: 0.5,
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    metadata: [
      {name: 'description', content: 'Documentation for OpenProxyAI — the enterprise LLM proxy and AI control plane. Setup, API reference, policies, security, and deployment guides.'},
      {name: 'og:type', content: 'website'},
      {name: 'og:site_name', content: 'OpenProxyAI Docs'},
      {name: 'twitter:card', content: 'summary_large_image'},
    ],
    colorMode: {
      defaultMode: 'dark',
      disableSwitch: true,
      respectPrefersColorScheme: false,
    },
    navbar: {
      title: 'OpenProxyAI',
      logo: {
        alt: 'OpenProxyAI logo',
        src: 'img/logo.svg',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: 'Docs',
        },
        {
          href: 'https://openproxy.ai',
          label: '← Back to site',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Product',
          items: [
            {label: 'Product', href: 'https://openproxy.ai/product'},
            {label: 'Security', href: 'https://openproxy.ai/security'},
            {label: 'Providers', href: 'https://openproxy.ai/providers'},
            {label: 'Pricing', href: 'https://openproxy.ai/pricing'},
          ],
        },
        {
          title: 'Docs',
          items: [
            {label: 'Getting Started', to: '/'},
            {label: 'API Reference', to: '/api-reference/overview'},
          ],
        },
      ],
      copyright: `© ${new Date().getFullYear()} OpenProxyAI`,
    },
    prism: {
      theme: prismThemes.oneDark,
      darkTheme: prismThemes.oneDark,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
