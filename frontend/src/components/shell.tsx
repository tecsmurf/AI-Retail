"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  Activity, BarChart3, Clapperboard, LayoutDashboard, Lightbulb, LogOut, Menu, Route, Settings2, X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { DashboardProvider } from "./dashboard";
import { useSession } from "./session";
import { Loading } from "./ui";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard, mobile: true },
  { href: "/analytics", label: "Analytics", icon: BarChart3, mobile: true },
  { href: "/journeys", label: "Journeys", icon: Route, mobile: false },
  { href: "/insights", label: "Insights", icon: Lightbulb, mobile: true },
  { href: "/videos", label: "Videos", icon: Clapperboard, mobile: true },
  { href: "/setup", label: "Cameras & zones", icon: Settings2, mobile: false },
  { href: "/system", label: "System", icon: Activity, mobile: false },
];

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2">
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-purple-600 text-sm font-bold text-white">P</span>
      <span className="font-semibold tracking-tight">PurpleSol</span>
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, checked, logout } = useSession();
  const [moreOpen, setMoreOpen] = useState(false);

  if (pathname.startsWith("/login")) return <>{children}</>;
  if (!checked || !user) {
    return (
      <div className="grid min-h-dvh place-items-center">
        <Loading label="Checking your session" />
      </div>
    );
  }

  return (
    <DashboardProvider>
      <div className="min-h-dvh lg:flex">
        {/* Desktop sidebar */}
        <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r border-[var(--border-color)] bg-[var(--bg-secondary)] p-4 lg:flex">
          <Brand />
          <nav className="mt-6 flex flex-1 flex-col gap-1">
            {NAV.map(({ href, label, icon: Icon }) => (
              <Link key={href} href={href}
                className={cn("flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-[var(--text-secondary)] hover:bg-white/5 hover:text-[var(--text-primary)]",
                  isActive(pathname, href) && "bg-purple-500/10 text-purple-200")}>
                <Icon className="h-4 w-4" /> {label}
              </Link>
            ))}
          </nav>
          <div className="border-t border-[var(--border-color)] pt-3 text-xs text-[var(--text-muted)]">
            <div className="truncate">{user.email}</div>
            <div className="mt-0.5 capitalize">{user.role}</div>
            <button onClick={() => void logout()} className="mt-2 flex items-center gap-2 text-[var(--text-secondary)] hover:text-white">
              <LogOut className="h-3.5 w-3.5" /> Sign out
            </button>
            <button onClick={() => void logout(true)} className="mt-1.5 text-left text-[var(--text-muted)] hover:text-white">
              Sign out on all devices
            </button>
          </div>
        </aside>

        {/* Mobile top bar */}
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-[var(--border-color)] bg-[var(--bg-primary)]/90 px-4 backdrop-blur lg:hidden">
          <Brand />
          <button aria-label="Menu" onClick={() => setMoreOpen(true)} className="grid h-10 w-10 place-items-center rounded-lg hover:bg-white/5">
            <Menu className="h-5 w-5" />
          </button>
        </header>

        <main className="mx-auto w-full max-w-7xl flex-1 px-4 pb-28 pt-4 sm:px-6 lg:pb-10 lg:pt-8">{children}</main>

        {/* Mobile bottom navigation */}
        <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-[var(--border-color)] bg-[var(--bg-secondary)]/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden">
          {NAV.filter((n) => n.mobile).map(({ href, label, icon: Icon }) => (
            <Link key={href} href={href}
              className={cn("flex h-16 flex-col items-center justify-center gap-1 text-[11px] text-[var(--text-muted)]",
                isActive(pathname, href) && "text-purple-300")}>
              <Icon className="h-5 w-5" /> {label}
            </Link>
          ))}
        </nav>

        {/* Mobile full menu */}
        {moreOpen && (
          <div className="fixed inset-0 z-40 bg-black/60 lg:hidden" onClick={() => setMoreOpen(false)}>
            <div className="absolute inset-y-0 right-0 flex w-72 max-w-[85vw] flex-col bg-[var(--bg-secondary)] p-4" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between">
                <Brand />
                <button aria-label="Close menu" onClick={() => setMoreOpen(false)} className="grid h-10 w-10 place-items-center rounded-lg hover:bg-white/5">
                  <X className="h-5 w-5" />
                </button>
              </div>
              <nav className="mt-4 flex flex-col gap-1">
                {NAV.map(({ href, label, icon: Icon }) => (
                  <Link key={href} href={href} onClick={() => setMoreOpen(false)}
                    className={cn("flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm",
                      isActive(pathname, href) ? "bg-purple-500/10 text-purple-200" : "text-[var(--text-secondary)]")}>
                    <Icon className="h-4 w-4" /> {label}
                  </Link>
                ))}
              </nav>
              <div className="mt-auto border-t border-[var(--border-color)] pt-3 text-xs text-[var(--text-muted)]">
                <div className="truncate">{user.email} · {user.role}</div>
                <button onClick={() => void logout()} className="mt-3 flex min-h-10 items-center gap-2 text-[var(--text-secondary)]">
                  <LogOut className="h-4 w-4" /> Sign out
                </button>
                <button onClick={() => void logout(true)} className="flex min-h-10 items-center text-[var(--text-muted)]">
                  Sign out on all devices
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardProvider>
  );
}
