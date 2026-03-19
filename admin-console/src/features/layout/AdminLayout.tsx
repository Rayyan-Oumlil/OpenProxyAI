import { useState, useEffect, useCallback } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  List,
  Shield,
  ShieldCheck,
  ArrowLeftRight,
  Key,
  Plug2,
  Sliders,
  Users,
  Building2,
  ChevronDown,
  ChevronRight,
  PanelLeftClose,
  PanelLeftOpen,
  LogOut,
  CreditCard,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { useAuth } from "../../state/AuthContext";

type NavItem = { label: string; to: string; icon: React.ElementType };
type NavGroup = { label: string; icon: React.ElementType; items: NavItem[] };
type NavEntry = NavItem | ({ group: true } & NavGroup);

const NAV: NavEntry[] = [
  { label: "Dashboard", to: "/", icon: LayoutDashboard },
  { label: "Request Logs", to: "/logs", icon: List },
  {
    group: true,
    label: "Monitor",
    icon: Shield,
    items: [
      { label: "Policy Events", to: "/policy-events", icon: Shield },
      { label: "Reconciliation", to: "/reconciliation", icon: ArrowLeftRight },
      { label: "Audit Log", to: "/audit", icon: ShieldCheck },
    ],
  },
  {
    group: true,
    label: "Settings",
    icon: Sliders,
    items: [
      { label: "API Keys", to: "/api-keys", icon: Key },
      { label: "Provider Keys", to: "/provider-keys", icon: Plug2 },
      { label: "Policy Config", to: "/policy", icon: Sliders },
      { label: "Billing", to: "/billing", icon: CreditCard },
    ],
  },
  {
    group: true,
    label: "Team",
    icon: Users,
    items: [
      { label: "Users & Roles", to: "/users-roles", icon: Users },
      { label: "Organization", to: "/organization-settings", icon: Building2 },
    ],
  },
];

function SidebarLink({
  item,
  collapsed,
  indent = false,
}: {
  item: NavItem;
  collapsed: boolean;
  indent?: boolean;
}) {
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      end={item.to === "/"}
      title={collapsed ? item.label : undefined}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors duration-100",
          "hover:bg-[rgba(44,109,191,0.08)]",
          isActive
            ? "bg-[rgba(44,109,191,0.12)] text-[var(--accent-sky)] font-medium"
            : "text-[#3e4250]",
          indent && !collapsed && "ml-2",
          collapsed && "justify-center"
        )
      }
    >
      <Icon size={16} className="shrink-0" />
      {!collapsed && <span className="truncate">{item.label}</span>}
    </NavLink>
  );
}

function SidebarGroup({
  group,
  collapsed,
  expanded,
  onToggle,
}: {
  group: NavGroup;
  collapsed: boolean;
  expanded: boolean;
  onToggle: () => void;
}) {
  const location = useLocation();
  const GroupIcon = group.icon;
  const isAnyActive = group.items.some((item) =>
    item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to)
  );

  if (collapsed) {
    return (
      <>
        {group.items.map((item) => (
          <SidebarLink key={item.to} item={item} collapsed={collapsed} />
        ))}
      </>
    );
  }

  return (
    <div>
      <button
        type="button"
        onClick={onToggle}
        className={cn(
          "w-full flex items-center gap-2.5 rounded-md px-2.5 py-2 text-xs font-semibold uppercase tracking-wider transition-colors",
          "hover:bg-[rgba(44,109,191,0.06)]",
          isAnyActive ? "text-[var(--accent-sky)]" : "text-[var(--muted)]"
        )}
      >
        <GroupIcon size={14} className="shrink-0" />
        <span className="flex-1 text-left">{group.label}</span>
        {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
      </button>
      {expanded && (
        <div className="mt-0.5 flex flex-col gap-0.5">
          {group.items.map((item) => (
            <SidebarLink key={item.to} item={item} collapsed={collapsed} indent />
          ))}
        </div>
      )}
    </div>
  );
}

const DEFAULT_EXPANDED = ["Monitor", "Settings", "Team"];

export function AdminLayout() {
  const { user, logout } = useAuth();

  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem("sidebarCollapsed") === "true";
    } catch {
      return false;
    }
  });

  const [expandedGroups, setExpandedGroups] = useState<string[]>(() => {
    try {
      const stored = localStorage.getItem("sidebarExpandedGroups");
      return stored ? JSON.parse(stored) : DEFAULT_EXPANDED;
    } catch {
      return DEFAULT_EXPANDED;
    }
  });

  useEffect(() => {
    localStorage.setItem("sidebarCollapsed", String(collapsed));
  }, [collapsed]);

  useEffect(() => {
    localStorage.setItem("sidebarExpandedGroups", JSON.stringify(expandedGroups));
  }, [expandedGroups]);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "b") {
      e.preventDefault();
      setCollapsed((c) => !c);
    }
  }, []);

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  function toggleGroup(label: string) {
    setExpandedGroups((prev) =>
      prev.includes(label) ? prev.filter((g) => g !== label) : [...prev, label]
    );
  }

  return (
    <div className="admin-shell" style={{ gridTemplateColumns: collapsed ? "48px 1fr" : "208px 1fr" }}>
      <aside
        className={cn(
          "left-rail transition-all duration-200 overflow-hidden",
          collapsed ? "p-1.5" : "p-3"
        )}
        style={{ borderRight: "1px solid var(--line)", background: "linear-gradient(180deg, #fff8ed 0%, #fffdf8 100%)" }}
      >
        <div className={cn("flex items-center mb-4", collapsed ? "justify-center" : "justify-between px-1")}>
          {!collapsed && (
            <span className="font-bold text-[0.95rem] tracking-tight text-foreground">
              OpenProxy<span style={{ color: "var(--accent-sky)" }}>AI</span>
            </span>
          )}
          <button
            type="button"
            title={collapsed ? "Expand sidebar (Ctrl+B)" : "Collapse sidebar (Ctrl+B)"}
            onClick={() => setCollapsed((c) => !c)}
            className="rounded-md p-1 text-muted hover:text-foreground hover:bg-[rgba(0,0,0,0.06)] transition-colors"
            style={{ border: "none", background: "transparent" }}
          >
            {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          </button>
        </div>

        <nav className="flex flex-col gap-0.5" aria-label="Main Navigation">
          {NAV.map((entry) => {
            if ("group" in entry && entry.group) {
              return (
                <SidebarGroup
                  key={entry.label}
                  group={entry}
                  collapsed={collapsed}
                  expanded={expandedGroups.includes(entry.label)}
                  onToggle={() => toggleGroup(entry.label)}
                />
              );
            }
            return (
              <SidebarLink key={(entry as NavItem).to} item={entry as NavItem} collapsed={collapsed} />
            );
          })}
        </nav>

        <div
          className={cn("mt-auto pt-3 border-t", collapsed ? "flex justify-center" : "")}
          style={{ borderColor: "var(--line)" }}
        >
          {collapsed ? (
            <button
              type="button"
              title="Sign out"
              onClick={logout}
              className="rounded-md p-1.5 text-muted hover:text-foreground hover:bg-[rgba(0,0,0,0.06)] transition-colors"
              style={{ border: "none", background: "transparent" }}
            >
              <LogOut size={15} />
            </button>
          ) : (
            <div className="profile-box">
              <p className="text-sm font-medium truncate">{user?.name ?? user?.email ?? "Unknown"}</p>
              <small>{user?.role ?? "member"}</small>
              <button
                type="button"
                onClick={logout}
                className="flex items-center gap-1.5 text-xs text-muted hover:text-foreground transition-colors"
                style={{ border: "none", background: "transparent", padding: 0 }}
              >
                <LogOut size={13} />
                Sign out
              </button>
            </div>
          )}
        </div>
      </aside>

      <main className="content-area overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
