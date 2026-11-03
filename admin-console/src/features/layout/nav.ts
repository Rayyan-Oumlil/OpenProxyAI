import {
  BarChart3,
  Building2,
  CreditCard,
  FlaskConical,
  Key,
  LayoutDashboard,
  List,
  Plug2,
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
 * Four groups answer four questions: what is happening (Observe), what is allowed (Govern),
 * what is connected (Connect), who runs it (Admin). New pages slot into a group, not the top level.
 */
export const NAV_GROUPS: NavGroup[] = [
  {
    id: "observe",
    label: "Observe",
    items: [
      { label: "Dashboard", to: "/", icon: LayoutDashboard },
      { label: "Request logs", to: "/logs", icon: List },
      { label: "Audit log", to: "/audit", icon: ShieldCheck },
      { label: "Playground", to: "/playground", icon: FlaskConical },
    ],
  },
  {
    id: "govern",
    label: "Govern",
    items: [
      { label: "Policy", to: "/policy", icon: Sliders },
      { label: "API keys", to: "/api-keys", icon: Key },
    ],
  },
  {
    id: "connect",
    label: "Connect",
    items: [
      { label: "Provider keys", to: "/provider-keys", icon: Plug2 },
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
