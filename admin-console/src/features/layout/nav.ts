import {
  BarChart3,
  Boxes,
  Database,
  Building2,
  CreditCard,
  Activity,
  FlaskConical,
  Gauge,
  ListChecks,
  Key,
  LayoutDashboard,
  List,
  MessagesSquare,
  Puzzle,
  Search,
  Star,
  Plug2,
  Server,
  ShieldCheck,
  Sliders,
  Users,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  to: string;
  icon: LucideIcon;
}

export interface NavGroup {
  id: string;
  label: string;
  items: NavItem[];
}

/**
 * Five groups answer five questions: what is happening (Observe), what is allowed (Govern),
 * is a change better (Evaluate), what is connected (Connect), who runs it (Admin). New pages slot into a group, not the top level.
 */
export const NAV_GROUPS: NavGroup[] = [
  {
    id: "observe",
    label: "Observe",
    items: [
      { label: "Dashboard", to: "/", icon: LayoutDashboard },
      { label: "Request logs", to: "/logs", icon: List },
      { label: "Audit log", to: "/audit", icon: ShieldCheck },
      { label: "Analytics query", to: "/analytics-query", icon: Search },
      { label: "Playground", to: "/playground", icon: FlaskConical },
      { label: "Conversations", to: "/conversations", icon: MessagesSquare },
    ],
  },
  {
    id: "govern",
    label: "Govern",
    items: [
      { label: "Policy", to: "/policy", icon: Sliders },
      { label: "API keys", to: "/api-keys", icon: Key },
      { label: "Model registry", to: "/model-registry", icon: Boxes },
      { label: "Policy plugins", to: "/policy-plugins", icon: Puzzle },
    ],
  },
  {
    id: "evaluate",
    label: "Evaluate",
    items: [
      { label: "Scores", to: "/scores", icon: Star },
      { label: "Datasets", to: "/datasets", icon: Database },
      { label: "Evaluators", to: "/evaluators", icon: ListChecks },
      { label: "Eval runs", to: "/eval-runs", icon: Gauge },
    ],
  },
  {
    id: "connect",
    label: "Connect",
    items: [
      { label: "Provider keys", to: "/provider-keys", icon: Plug2 },
      { label: "Provider health", to: "/provider-health", icon: Activity },
      { label: "MCP servers", to: "/mcp-servers", icon: Server },
      { label: "Experiments", to: "/experiments", icon: BarChart3 },
    ],
  },
  {
    id: "admin",
    label: "Admin",
    items: [
      { label: "Teams", to: "/teams", icon: Users },
      { label: "Users and roles", to: "/users-roles", icon: Users },
      { label: "Organization", to: "/organization-settings", icon: Building2 },
      { label: "Billing", to: "/billing", icon: CreditCard },
    ],
  },
];
