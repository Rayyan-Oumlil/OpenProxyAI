import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

/**
 * Three sidebars, one per top-bar tab (Documentation, Guides, API Reference).
 * Sections are always open: the label is a heading, not a toggle.
 */
const sidebars: SidebarsConfig = {
  docsSidebar: [
    {
      type: 'category',
      collapsible: false,
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
      collapsible: false,
      label: 'Core Concepts',
      items: [
        'core-concepts/request-pipeline',
        'core-concepts/caching',
        'core-concepts/policies-and-guardrails',
        'core-concepts/provider-routing',
        'core-concepts/behavior-settings',
        'core-concepts/rate-limiting-and-budgets',
      ],
    },
    {
      type: 'category',
      collapsible: false,
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
      collapsible: false,
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
      collapsible: false,
      label: 'Admin Console',
      items: [
        'admin-console/overview',
        'admin-console/managing-teams',
        'admin-console/managing-policies',
        'admin-console/evaluating-changes',
        'admin-console/billing',
      ],
    },
    {
      type: 'category',
      collapsible: false,
      label: 'Resources',
      items: ['changelog'],
    },
  ],
  guidesSidebar: [
    {
      type: 'category',
      collapsible: false,
      label: 'Guides',
      items: [
        'guides/deploying-with-docker-compose',
        'guides/deploying-with-helm',
        'guides/configuring-sso',
        'guides/configuring-scim',
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
        'guides/policy-plugins',
      ],
    },
  ],
  apiSidebar: [
    {
      type: 'category',
      collapsible: false,
      label: 'API Reference',
      items: [
        'api-reference/overview',
        'api-reference/errors-and-status-codes',
        'api-reference/chat-completions',
        'api-reference/embeddings',
        'api-reference/more-endpoints',
        'api-reference/realtime',
        'api-reference/batches',
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
  ],
};

export default sidebars;
