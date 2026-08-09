"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLayoutEffect, ViewTransition } from "react";
import { useAuth } from "@/lib/auth";
import { belongsToAgent, useAgentSync } from "@/lib/store";
import {
  HomeIcon,
  InboxIcon,
  LogoMark,
  SlidersIcon,
  UserIcon,
} from "@/components/Icons";

const navigation = [
  { href: "/", label: "Inicio", icon: HomeIcon },
  { href: "/setup", label: "Mi agente", icon: SlidersIcon },
  { href: "/bandeja", label: "Decisiones", icon: InboxIcon },
];

function isCurrent(pathname: string, href: string) {
  if (href === "/") return pathname === href || pathname.startsWith("/chat/");
  return pathname.startsWith(href);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { signedIn, agentId, attachAgent } = useAuth();
  const { sessions } = useAgentSync();
  const pendingCount = sessions.filter(
    (session) =>
      belongsToAgent(session, agentId) &&
      session.status === "PENDING_HUMAN_APPROVAL",
  ).length;

  useLayoutEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });

    const frame = window.requestAnimationFrame(() => {
      window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    });

    return () => window.cancelAnimationFrame(frame);
  }, [pathname]);

  return (
    <div className={`app-shell ${signedIn ? "is-authenticated" : "is-guest"}`}>
      <header className="app-header">
        <div className="header-inner">
          <Link href="/" className="brand" aria-label="AgentSync, ir al inicio">
            <LogoMark />
            <span className="brand-name">AgentSync</span>
          </Link>

          {signedIn ? (
            <nav className="desktop-nav" aria-label="Navegación principal">
              {navigation.map((item) => {
                const active = isCurrent(pathname, item.href);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`nav-link ${active ? "is-active" : ""}`}
                    aria-current={active ? "page" : undefined}
                  >
                    <Icon size={17} />
                    {item.label}
                    {item.href === "/bandeja" && pendingCount > 0 ? (
                      <span className="nav-count">{pendingCount}</span>
                    ) : null}
                  </Link>
                );
              })}
            </nav>
          ) : null}

          <div className="header-actions">
            <Link
              href="/perfil"
              className={`profile-button ${!signedIn ? "is-entry" : ""} ${pathname.startsWith("/perfil") ? "is-active" : ""}`}
              aria-label={signedIn ? "Abrir mi perfil" : "Ingresar o crear una cuenta"}
              title={signedIn ? "Mi perfil" : "Ingresar"}
            >
              <UserIcon size={19} />
              {!signedIn ? <span>Ingresar</span> : null}
            </Link>
          </div>
        </div>
      </header>

      <main className="app-main">
        <ViewTransition
          key={pathname}
          name="agentsync-page"
          share="page-swap"
          enter="page-swap"
          default="none"
        >
          <div className="page-transition-content">{children}</div>
        </ViewTransition>
      </main>

      <footer className="app-footer">
        <span>AgentSync · entorno de demostración</span>
        <span>Los límites duros nunca se negocian.</span>
      </footer>

      {signedIn ? (
        <nav className="mobile-nav" aria-label="Navegación móvil">
          {navigation.map((item) => {
            const active = isCurrent(pathname, item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={active ? "is-active" : ""}
                aria-current={active ? "page" : undefined}
              >
                <span className="mobile-icon-wrap">
                  <Icon size={19} />
                  {item.href === "/bandeja" && pendingCount > 0 ? (
                    <span className="mobile-count">{pendingCount}</span>
                  ) : null}
                </span>
                <small>{item.label}</small>
              </Link>
            );
          })}
        </nav>
      ) : null}
    </div>
  );
}
