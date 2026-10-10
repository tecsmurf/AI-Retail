"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import type { Store } from "@/lib/types";
import { addDays, todayIn } from "@/lib/utils";
import { useSession } from "./session";

export type DataMode = "real" | "all";

interface Filters {
  storeId: string | null;
  start: string | null; // null = default (last 7 days in store time)
  end: string | null;
  data: DataMode;
}

interface DashboardValue {
  stores: Store[] | undefined;
  storesError: Error | undefined;
  reloadStores: () => void;
  store: Store | undefined;
  start: string;
  end: string;
  data: DataMode;
  isDefaultRange: boolean;
  setStore: (id: string) => void;
  setRange: (start: string, end: string) => void;
  resetRange: () => void;
  setData: (d: DataMode) => void;
  /** Query parameters for analytics endpoints. */
  query: { start: string; end: string; data: DataMode };
}

const KEY = "purplesol.filters.v1";
const DashboardContext = createContext<DashboardValue | null>(null);

function readSaved(): Filters {
  const empty: Filters = { storeId: null, start: null, end: null, data: "real" };
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? { ...empty, ...JSON.parse(raw) } : empty;
  } catch {
    return empty;
  }
}

export function DashboardProvider({ children }: { children: React.ReactNode }) {
  const { user } = useSession();
  const storesRes = useResource(user ? `stores:${user.id}` : null, (signal) => api<Store[]>("/api/stores", { signal }));
  const [filters, setFilters] = useState<Filters>({ storeId: null, start: null, end: null, data: "real" });

  useEffect(() => {
    // Restore after hydration (localStorage is not available on the server).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFilters(readSaved());
  }, []);

  const update = useCallback((patch: Partial<Filters>) => {
    setFilters((f) => {
      const next = { ...f, ...patch };
      try {
        window.localStorage.setItem(KEY, JSON.stringify(next));
      } catch {
        /* private mode */
      }
      return next;
    });
  }, []);

  const stores = storesRes.data;
  const store = stores?.find((s) => s.id === filters.storeId) ?? stores?.[0];
  const tz = store?.timezone ?? "Asia/Kolkata";
  const end = filters.end ?? todayIn(tz);
  const start = filters.start ?? addDays(end, -6);

  const value = useMemo<DashboardValue>(
    () => ({
      stores,
      storesError: storesRes.error,
      reloadStores: storesRes.reload,
      store,
      start,
      end,
      data: filters.data,
      isDefaultRange: filters.start === null,
      setStore: (id) => update({ storeId: id }),
      setRange: (s, e) => update({ start: s, end: e }),
      resetRange: () => update({ start: null, end: null }),
      setData: (d) => update({ data: d }),
      query: { start, end, data: filters.data },
    }),
    [stores, storesRes.error, storesRes.reload, store, start, end, filters.data, filters.start, update],
  );
  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}

export function useDashboard(): DashboardValue {
  const v = useContext(DashboardContext);
  if (!v) throw new Error("useDashboard outside DashboardProvider");
  return v;
}
