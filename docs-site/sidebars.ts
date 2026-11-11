import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

/**
 * Creating a sidebar enables you to:
 - create an ordered group of docs
 - render a sidebar for each doc of that group
 - provide next/previous navigation

 The sidebars can be generated from the filesystem, or explicitly defined here.

 Create as many sidebars as you want.
 */
const sidebars: SidebarsConfig = {
  docsSidebar: [
    {
      type: 'category',
      label: 'Getting Started',
      items: [
        'getting-started/introduction',
        'getting-started/quickstart',
        'getting-started/authentication',
        'getting-started/environment-flags',
      ],
    },
    {
      type: 'category',
      label: 'Core Concepts',
      items: [
        'core-concepts/request-pipeline',
        'core-concepts/caching',
        'core-concepts/policies-and-guardrails',
        'core-concepts/provider-routing',
        'core-concepts/rate-limiting-and-budgets',
      ],
    },
    {
      type: 'category',
      label: 'Guides',
      items: [
        'guides/deploying-with-docker-compose',
        'guides/deploying-with-helm',
        'guides/configuring-sso',
        'guides/compliance-templates',
        'guides/webhooks',
        'guides/mcp-gateway',
        'guides/prompt-playground',
        'guides/semantic-cache-tuning',
        'guides/data-residency',
        'guides/payload-capture',
        'guides/adaptive-experiments',
        'guides/prompt-promotion',
        'guides/conversations',
        'guides/telemetry-and-siem',
        'guides/secrets-from-vault',
      ],
    },
    {
      type: 'category',
      label: 'Security & Compliance',
      items: [
        'security/trust-center',
        'security/audit-logging',
        'security/row-level-security',
        'security/hipaa-template',
        'security/pci-template',
        'security/fedramp-template',
      ],
    },
    {
      type: 'category',
      label: 'Integrations',
      items: [
        'integrations/openai-sdk-compatibility',
        'integrations/python-sdk',
        'integrations/typescript-sdk',
        'integrations/langchain',
      ],
    },
    {
      type: 'category',
      label: 'API Reference',
      items: [
        'api-reference/overview',
        'api-reference/errors-and-status-codes',
        'api-reference/chat-completions',
        'api-reference/embeddings',
        'api-reference/more-endpoints',
        'api-reference/feedback',
        'api-reference/datasets',
        'api-reference/eval-runs',
        'api-reference/analytics-query',
        'api-reference/conversations',
        'api-reference/models',
        'api-reference/api-keys',
        'api-reference/provider-keys',
        'api-reference/organizations',
        'api-reference/teams',
        'api-reference/analytics',
        'api-reference/webhooks-api',
      ],
    },
    {
      type: 'category',
      label: 'Admin Console',
      items: [
        'admin-console/overview',
        'admin-console/managing-teams',
        'admin-console/managing-policies',
        'admin-console/evaluating-changes',
        'admin-console/billing',
      ],
    },
    'changelog',
  ],
};

export default sidebars;
