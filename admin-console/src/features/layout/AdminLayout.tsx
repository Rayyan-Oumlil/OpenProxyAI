import { useCallback, useEffect, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { LogOut, Menu, PanelLeftClose, PanelLeftOpen, X } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { ThemeToggle } from "../../components/ui/ThemeToggle";
import { cn } from "../../lib/utils";
import { DESKTOP_QUERY, useMediaQuery } from "../../lib/useMediaQuery";
import { useAuth } from "../../state/AuthContext";
import { NAV_GROUPS } from "./nav";

const COLLAPSE_KEY = "sidebarCollapsed";

function readCollapsed(): boolean {
  try {
    return window.localStorage.getItem(COLLAPSE_KEY) === "true";
  } catch {
    return false;
  }
}

function Wordmark() {
  return (
    <span className="wordmark">
      OpenProxy<span>AI</span>
    </span>
  );
}

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapsed?: () => void;
  onClose?: () => void;
}

function Sidebar({ collapsed, onToggleCollapsed, onClose }: SidebarProps) {
  const { user, logout } = useAuth();
  const identity = user?.name ?? user?.email ?? "Unknown user";

  return (
    <>
      <div className="rail__head">
        {collapsed ? null : <Wordmark />}
        {onToggleCollapsed ? (
          <button
            type="button"
            className="icon-btn"
            onClick={onToggleCollapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar (Ctrl+B)" : "Collapse sidebar (Ctrl+B)"}
          >
            {collapsed ? <PanelLeftOpen size={16} aria-hidden="true" /> : <PanelLeftClose size={16} aria-hidden="true" />}
          </button>
        ) : null}
        {onClose ? (
          <Dialog.Close className="icon-btn" aria-label="Close navigation">
            <X size={16} aria-hidden="true" />
          </Dialog.Close>
        ) : null}
      </div>

      <nav className="rail__nav" aria-label="Main">
        {NAV_GROUPS.map((group) => (
          <section key={group.id} aria-labelledby={`nav-${group.id}`}>
            <h2 id={`nav-${group.id}`} className={cn("nav-group", collapsed && "sr-only")}>
              {group.label}
            </h2>
            <ul>
              {group.items.map(({ label, to, icon: Icon }) => (
                <li key={to}>
                  <NavLink to={to} end={to === "/"} className="nav-item" title={collapsed ? label : undefined}>
                    <Icon size={16} aria-hidden="true" />
                    <span className={cn(collapsed && "sr-only")}>{label}</span>
                  </NavLink>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </nav>

      <div className="rail__foot">
        <ThemeToggle compact={collapsed} />
        {collapsed ? null : (
          <div className="whoami">
            <p className="whoami__name" title={identity}>
              {identity}
            </p>
            <p className="whoami__role">{user?.role ?? "member"}</p>
          </div>
        )}
        <button type="button" className="nav-item nav-item--button" onClick={logout} title={collapsed ? "Sign out" : undefined}>
          <LogOut size={16} aria-hidden="true" />
          <span className={cn(collapsed && "sr-only")}>Sign out</span>
        </button>
      </div>
    </>
  );
}

export function AdminLayout() {
  const isDesktop = useMediaQuery(DESKTOP_QUERY);
  const location = useLocation();
  const [collapsed, setCollapsed] = useState<boolean>(readCollapsed);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    try {
      window.localStorage.setItem(COLLAPSE_KEY, String(collapsed));
    } catch {
      // Preference just will not persist.
    }
  }, [collapsed]);

  // Following a link, or growing the window to desktop width, closes the drawer.
  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname, isDesktop]);

  const onKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (isDesktop && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "b") {
        event.preventDefault();
        setCollapsed((value) => !value);
      }
    },
    [isDesktop],
  );

  useEffect(() => {
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onKeyDown]);

  return (
    <div className="shell" data-collapsed={isDesktop && collapsed}>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>

      {isDesktop ? (
        <aside className="rail" aria-label="Sidebar">
          <Sidebar collapsed={collapsed} onToggleCollapsed={() => setCollapsed((value) => !value)} />
        </aside>
      ) : (
        <>
          <header className="topbar">
            <button
              ref={menuButton}
              type="button"
              className="icon-btn"
              aria-label="Open navigation"
              aria-expanded={drawerOpen}
              aria-controls="nav-drawer"
              onClick={() => setDrawerOpen(true)}
            >
              <Menu size={18} aria-hidden="true" />
            </button>
            <Wordmark />
          </header>
          <Dialog.Root open={drawerOpen} onOpenChange={setDrawerOpen}>
            <Dialog.Portal>
              <Dialog.Overlay className="drawer-scrim" />
              <Dialog.Content
                id="nav-drawer"
                className="rail rail--drawer"
                aria-describedby={undefined}
                onCloseAutoFocus={(event) => {
                  // Opened by state rather than a Dialog.Trigger, so hand focus back to the menu button ourselves.
                  event.preventDefault();
                  menuButton.current?.focus();
                }}
              >
                <Dialog.Title className="sr-only">Navigation</Dialog.Title>
                <Sidebar collapsed={false} onClose={() => setDrawerOpen(false)} />
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
        </>
      )}

      <main id="main-content" className="main" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}
