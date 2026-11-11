"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, setUnauthorizedHandler } from "@/lib/api";
import type { Me } from "@/lib/types";

interface SessionValue {
  user: Me | null;
  checked: boolean;
  isAdmin: boolean;
  /** May upload recordings and start, cancel or retry processing. */
  canUpload: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: (everywhere?: boolean) => Promise<void>;
  refresh: () => Promise<void>;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [checked, setChecked] = useState(false);
  const router = useRouter();
  const pathname = usePathname();

  const refresh = useCallback(async () => {
    try {
      setUser(await api<Me>("/api/auth/me"));
    } catch {
      setUser(null);
    } finally {
      setChecked(true);
    }
  }, []);

  useEffect(() => {
    let alive = true;
    api<Me>("/api/auth/me").then(
      (u) => alive && (setUser(u), setChecked(true)),
      () => alive && (setUser(null), setChecked(true)),
    );
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      if (!window.location.pathname.startsWith("/login")) {
        router.replace(`/login?next=${encodeURIComponent(window.location.pathname)}`);
      }
    });
    return () => setUnauthorizedHandler(null);
  }, [router]);

  useEffect(() => {
    if (checked && !user && !pathname.startsWith("/login")) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [checked, user, pathname, router]);

  const login = useCallback(async (email: string, password: string) => {
    setUser(await api<Me>("/api/auth/login", { json: { email, password } }));
    setChecked(true);
  }, []);

  const logout = useCallback(async (everywhere = false) => {
    try {
      await api(everywhere ? "/api/auth/logout-everywhere" : "/api/auth/logout", { method: "POST" });
    } finally {
      setUser(null);
      router.replace("/login");
    }
  }, [router]);

  const value = useMemo(
    () => ({ user, checked, isAdmin: !!user?.is_admin, canUpload: !!user?.can_upload, login, logout, refresh }),
    [user, checked, login, logout, refresh],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const v = useContext(SessionContext);
  if (!v) throw new Error("useSession outside SessionProvider");
  return v;
}
