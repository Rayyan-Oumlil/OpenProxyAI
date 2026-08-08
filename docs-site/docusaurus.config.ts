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

  url: 'https://docs.openproxyai.com',
  baseUrl: '/',

  organizationName: 'openproxyai',
  projectName: 'openproxyai-docs',

  onBrokenLinks: 'warn',
  onBrokenAnchors: 'warn',

  markdown: {
    mermaid: true,
  },
  themes: ['@docusaurus/theme-mermaid'],

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
        blog: {
          routeBasePath: 'blog',
          blogTitle: 'OpenProxyAI Blog',
          blogDescription: 'Engineering notes on running an LLM control plane — architecture, security, and what actually happens inside the request pipeline.',
          postsPerPage: 10,
          blogSidebarTitle: 'Recent posts',
          blogSidebarCount: 10,
          showReadingTime: true,
          feedOptions: {
            type: ['rss', 'atom'],
            xslt: true,
            title: 'OpenProxyAI Blog',
            description: 'Engineering notes on running an LLM control plane.',
            copyright: `Copyright © ${new Date().getFullYear()} OpenProxyAI`,
          },
          onInlineTags: 'warn',
          onInlineAuthors: 'warn',
          onUntruncatedBlogPosts: 'warn',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
        sitemap: {
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
    mermaid: {
      theme: {light: 'base', dark: 'base'},
      options: {
        themeVariables: {
          background: '#0f1117',
          primaryColor: '#141720',
          primaryTextColor: '#e7ecf2',
          primaryBorderColor: '#262b36',
          secondaryColor: '#0f1117',
          tertiaryColor: '#0b0d12',
          lineColor: '#35d399',
          textColor: '#e7ecf2',
          mainBkg: '#141720',
          nodeBorder: '#262b36',
          clusterBkg: '#0b0d12',
          clusterBorder: '#1c2029',
          edgeLabelBackground: '#0b0d12',
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
          actorBkg: '#141720',
          actorBorder: '#35d399',
          actorTextColor: '#e7ecf2',
          signalColor: '#a8b0bd',
          signalTextColor: '#e7ecf2',
          labelBoxBkgColor: '#141720',
          labelBoxBorderColor: '#35d399',
          labelTextColor: '#e7ecf2',
          noteBkgColor: '#0b0d12',
          noteTextColor: '#a8b0bd',
          noteBorderColor: '#1c2029',
        },
      },
    },
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
          to: '/blog',
          label: 'Blog',
          position: 'left',
        },
        {
          href: 'https://openproxyai.com',
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
            {label: 'Product', href: 'https://openproxyai.com/product'},
            {label: 'Security', href: 'https://openproxyai.com/security'},
            {label: 'Providers', href: 'https://openproxyai.com/providers'},
            {label: 'Pricing', href: 'https://openproxyai.com/pricing'},
          ],
        },
        {
          title: 'Docs',
          items: [
            {label: 'Getting Started', to: '/'},
            {label: 'API Reference', to: '/api-reference/overview'},
            {label: 'Blog', to: '/blog'},
          ],
        },
        {
          title: 'Trust',
          items: [
            {label: 'Trust Center', to: '/security/trust-center'},
            {label: 'Changelog', to: '/changelog'},
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
