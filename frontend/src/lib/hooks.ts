"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "./api";

export interface Resource<T> {
  data: T | undefined;
  error: ApiError | Error | undefined;
  loading: boolean;
  reload: () => void;
}

/** Fetch on mount and whenever `key` changes; `key === null` skips the request. */
export function useResource<T>(key: string | null, fetcher: (signal: AbortSignal) => Promise<T>): Resource<T> {
  const [state, setState] = useState<{ key: string | null; data?: T; error?: Error }>({ key: null });
  const [tick, setTick] = useState(0);
  const fetcherRef = useRef(fetcher);
  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  useEffect(() => {
    if (key === null) return;
    const ctrl = new AbortController();
    fetcherRef.current(ctrl.signal).then(
      (data) => setState({ key, data }),
      (error: Error) => {
        if (error.name !== "AbortError") setState((s) => ({ key, data: s.key === key ? s.data : undefined, error }));
      },
    );
    return () => ctrl.abort();
  }, [key, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  const current = state.key === key;
  return {
    data: current ? state.data : undefined,
    error: current ? state.error : undefined,
    loading: key !== null && (!current || (state.data === undefined && state.error === undefined)),
    reload,
  };
}

/** Re-run `fn` every `ms` while the page is visible. */
export function useInterval(fn: () => void, ms: number | null) {
  const ref = useRef(fn);
  useEffect(() => {
    ref.current = fn;
  });
  useEffect(() => {
    if (ms === null) return;
    const id = setInterval(() => {
      if (document.visibilityState === "visible") ref.current();
    }, ms);
    return () => clearInterval(id);
  }, [ms]);
}
