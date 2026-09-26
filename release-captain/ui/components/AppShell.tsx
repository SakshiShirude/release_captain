"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

type AppShellProps = {
  children: ReactNode;
};

type ThemeMode = "dark" | "light";

const THEME_STORAGE_KEY = "release-captain-theme";

function iconForTheme(theme: ThemeMode) {
  return theme === "dark" ? "☀" : "☾";
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const [theme, setTheme] = useState<ThemeMode>("dark");

  useEffect(() => {
    const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
    const nextTheme: ThemeMode = storedTheme === "light" ? "light" : "dark";
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  const sessionHref = useMemo(() => {
    return pathname.startsWith("/session/") ? pathname : "/";
  }, [pathname]);

  const auditHref = useMemo(() => {
    return pathname.startsWith("/session/") ? `${pathname}#audit-timeline` : "/";
  }, [pathname]);

  const navItems = [
    { href: "/", label: "New analysis", icon: "+", active: pathname === "/" },
    { href: sessionHref, label: "Release review", icon: "▣", active: pathname.startsWith("/session/") },
    { href: auditHref, label: "Audit timeline", icon: "≣", active: false },
  ];

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="sidebar-brand">
          <div className="brand-mark">RC</div>
          <div className="brand-copy">
            <strong>ShiftLeft</strong>
            <span>Release Captain</span>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Primary">
          {navItems.map((item) => (
            <Link key={`${item.label}-${item.href}`} href={item.href} className={`nav-link ${item.active ? "active" : ""}`}>
              <span className="nav-icon" aria-hidden="true">
                {item.icon}
              </span>
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-status">
            <span className="status-dot" aria-hidden="true" />
            <span>{pathname.startsWith("/session/") ? "Live review view" : "API backed"}</span>
          </div>

          <button
            type="button"
            className="theme-toggle"
            aria-pressed={theme === "light"}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            onClick={() => setTheme((value) => (value === "dark" ? "light" : "dark"))}
          >
            <span className="theme-toggle-icon" aria-hidden="true">
              {iconForTheme(theme)}
            </span>
            <span className="theme-toggle-copy">
              <strong>{theme === "dark" ? "Light" : "Dark"}</strong>
              <small>{theme === "dark" ? "Switch workspace palette" : "Return to low light palette"}</small>
            </span>
          </button>
        </div>
      </aside>

      <div className="app-main">{children}</div>
    </div>
  );
}
