import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const DASH = "—";

export function fmtInt(n: number | null | undefined): string {
  return n === null || n === undefined ? DASH : Math.round(n).toLocaleString("en-IN");
}

export function fmtCurrency(n: number | null | undefined): string {
  return n === null || n === undefined ? DASH : `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

export function fmtPercent(n: number | null | undefined): string {
  return n === null || n === undefined ? DASH : `${n.toFixed(1)}%`;
}

export function fmtDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return DASH;
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) {
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return s ? `${m}m ${s}s` : `${m}m`;
  }
  return `${(seconds / 3600).toFixed(1)}h`;
}

export function fmtBytes(n: number | null | undefined): string {
  if (n === null || n === undefined) return DASH;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(0)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
}

/** API datetimes without an offset are UTC (storage convention). */
export function parseUtc(s: string): Date {
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(s) ? s : `${s}Z`);
}

export function fmtDateTime(s: string | null | undefined, timeZone?: string): string {
  if (!s) return DASH;
  return parseUtc(s).toLocaleString("en-IN", {
    timeZone, day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

export function fmtTime(s: string | null | undefined, timeZone?: string): string {
  if (!s) return DASH;
  return parseUtc(s).toLocaleTimeString("en-IN", { timeZone, hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function relativeTime(s: string | null | undefined): string {
  if (!s) return DASH;
  const diff = (Date.now() - parseUtc(s).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

/** YYYY-MM-DD for "today" in a store's time zone. */
export function todayIn(timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}

export function addDays(isoDate: string, days: number): string {
  const d = new Date(`${isoDate}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export function fmtDay(isoDate: string): string {
  return new Date(`${isoDate}T00:00:00Z`).toLocaleDateString("en-IN", { timeZone: "UTC", day: "numeric", month: "short" });
}

export const SOURCE_LABELS: Record<string, string> = {
  cv: "CV (processed video)",
  api: "API",
  sample: "Sample file",
  demo: "Demo (synthetic)",
  legacy_cv: "Legacy v1 CV",
};

export const ZONE_COLORS: Record<string, string> = {
  SHELF: "#a855f7",
  DISPLAY: "#06b6d4",
  QUEUE: "#f59e0b",
  BILLING: "#10b981",
  ENTRANCE: "#f43f5e",
  EXIT: "#94a3b8",
  OTHER: "#64748b",
};
