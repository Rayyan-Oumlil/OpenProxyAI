import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../../state/AuthContext";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard" },
  { to: "/logs", label: "Request Logs" },
  { to: "/api-keys", label: "API Keys" },
  { to: "/users-roles", label: "Users & Roles" },
  { to: "/organization-settings", label: "Organization Settings" },
] as const;

export function AdminLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="admin-shell">
      <aside className="left-rail">
        <h2>OpenProxy</h2>
        <nav aria-label="Main Navigation">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => (isActive ? "nav-link is-active" : "nav-link")}
              end={item.to === "/"}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <section className="profile-box">
          <p>{user?.name ?? user?.email ?? "Unknown user"}</p>
          <small>{user?.role ?? "member"}</small>
          <button type="button" onClick={logout}>
            Sign out
          </button>
        </section>
      </aside>

      <main className="content-area">
        <Outlet />
      </main>
    </div>
  );
}

