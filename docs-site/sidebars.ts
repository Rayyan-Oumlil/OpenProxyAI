import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

/**
 * Three sidebars, one per top-bar tab (Documentation, Guides, API Reference).
 * Top-level sections are always open headings; the groups inside them
 * (sub-categories) fold, so a long section stays easy to scan.
 */
const group = (label: string, items: SidebarsConfig[string], collapsed = false) => ({
  type: 'category' as const,
  label,
  collapsed,
  items,
});

const section = (label: string, items: SidebarsConfig[string]) => ({
  type: 'category' as const,
  collapsible: false,
  label,
  items,
});

const sidebars: SidebarsConfig = {
  docsSidebar: [
    section('Getting Started', [
      'getting-started/introduction',
      'getting-started/quickstart',
      'getting-started/authentication',
      'getting-started/environment-flags',
    ]),
    section('Core Concepts', [
      'core-concepts/request-pipeline',
      'core-concepts/policies-and-guardrails',
      group(
        'Routing and cost',
        [
          'core-concepts/provider-routing',
          'core-concepts/caching',
          'core-concepts/rate-limiting-and-budgets',
          'core-concepts/behavior-settings',
        ],
        false,
      ),
    ]),
    section('Security and Compliance', [
      'security/trust-center',
      group('Data protection', ['security/row-level-security', 'security/data-residency'], false),
      'security/audit-logging',
      'security/compliance-templates',
    ]),
    section('Integrations', [
      'integrations/openai-sdk-and-frameworks',
      group('SDKs', ['integrations/python-sdk', 'integrations/typescript-sdk'], false),
    ]),
    section('Admin Console', [
      'admin-console/overview',
      'admin-console/managing-your-organization',
      group('Quality and batch work', ['admin-console/evaluating-changes', 'admin-console/batch-jobs'], false),
    ]),
    section('Resources', ['resources/glossary', 'resources/faq', 'resources/compare', 'changelog']),
  ],
  guidesSidebar: [
    section('Guides', [
      group('Deploy and sign in', ['guides/deployment', 'guides/sso-and-scim', 'guides/secrets-from-vault'], false),
      group('Agents and conversations', ['guides/mcp-gateway', 'guides/conversations'], false),
      group('Quality and prompts', ['guides/prompts', 'guides/adaptive-experiments'], false),
      group(
        'Observe and extend',
        ['guides/telemetry-and-siem', 'guides/payload-capture', 'guides/webhooks', 'guides/policy-plugins'],
        false,
      ),
    ]),
  ],
  apiSidebar: [
    section('API Reference', [
      group('Start here', ['api-reference/overview', 'api-reference/errors-and-status-codes'], false),
      group(
        'Inference',
        [
          'api-reference/chat-completions',
          'api-reference/other-endpoints',
          'api-reference/realtime',
          'api-reference/batches',
        ],
        false,
      ),
      group(
        'Quality',
        [
          'api-reference/feedback',
          'api-reference/datasets',
          'api-reference/eval-runs',
          'api-reference/conversations',
        ],
        false,
      ),
      'api-reference/analytics',
      group(
        'Administration',
        [
          'api-reference/organizations-teams-users',
          'api-reference/keys',
          'api-reference/mcp-admin',
        ],
        false,
      ),
    ]),
  ],
};

export default sidebars;
