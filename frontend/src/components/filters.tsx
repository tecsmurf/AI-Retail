"use client";

import { useState } from "react";
import { CalendarRange, Database, Store as StoreIcon } from "lucide-react";
import { api } from "@/lib/api";
import type { DataExtent } from "@/lib/types";
import { SOURCE_LABELS, addDays, cn, fmtDay, todayIn } from "@/lib/utils";
import { useDashboard } from "./dashboard";
import { Badge, Button, inputClass } from "./ui";

/** Store, date range and data-source controls shared by every analytics page. */
export function FilterBar() {
  const d = useDashboard();
  const [open, setOpen] = useState(false);
  const [jumping, setJumping] = useState(false);
  const [jumpNote, setJumpNote] = useState<string | null>(null);
  if (!d.stores) return null;
  if (d.stores.length === 0) return null;
  const tz = d.store?.timezone ?? "Asia/Kolkata";
  const today = todayIn(tz);

  async function jumpToLatest() {
    if (!d.store) return;
    setJumping(true);
    setJumpNote(null);
    try {
      const ext = await api<DataExtent>(`/api/analytics/${d.store.id}/data-extent`);
      const sources = Object.entries(ext.sources).filter(([k, v]) =>
        k !== "pos" && v.last_local_date && (d.data === "all" || k === "cv" || k === "api"));
      const last = sources.map(([, v]) => v.last_local_date as string).sort().pop();
      if (!last) {
        setJumpNote(d.data === "real" ? "No processed video data yet for this store." : "No data for this store.");
        return;
      }
      d.setRange(addDays(last, -6), last);
    } catch {
      setJumpNote("Could not look up where data exists.");
    } finally {
      setJumping(false);
    }
  }

  const presets: [string, string, string][] = [
    ["Today", today, today],
    ["7 days", addDays(today, -6), today],
    ["30 days", addDays(today, -29), today],
  ];

  return (
    <div className="mb-5 space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <label className="relative flex min-w-0 basis-full items-center sm:basis-auto">
          <StoreIcon className="pointer-events-none absolute left-3 h-4 w-4 text-[var(--text-muted)]" />
          <select aria-label="Store" value={d.store?.id ?? ""} onChange={(e) => d.setStore(e.target.value)}
            className={cn(inputClass, "pl-9 sm:w-64")}>
            {d.stores.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </label>
        <Button onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          <CalendarRange className="h-4 w-4" />
          {d.start === d.end ? fmtDay(d.start) : `${fmtDay(d.start)} – ${fmtDay(d.end)}`}
        </Button>
        <Button onClick={() => d.setData(d.data === "real" ? "all" : "real")}
          title="Real data = processed video and API events. All data adds the bundled sample, demo and legacy v1 records.">
          <Database className="h-4 w-4" />
          {d.data === "real" ? "Real data" : "All data"}
        </Button>
        <Button variant="ghost" onClick={() => void jumpToLatest()} disabled={jumping}>
          {jumping ? "Looking…" : "Jump to latest data"}
        </Button>
      </div>
      {open && (
        <div className="card flex flex-wrap items-end gap-2 p-3">
          {presets.map(([label, s, e]) => (
            <Button key={label} variant={d.start === s && d.end === e ? "primary" : "secondary"}
              onClick={() => { d.setRange(s, e); setOpen(false); }}>
              {label}
            </Button>
          ))}
          <input type="date" aria-label="Start date" value={d.start} max={d.end}
            onChange={(e) => e.target.value && d.setRange(e.target.value, d.end)} className={cn(inputClass, "w-auto")} />
          <input type="date" aria-label="End date" value={d.end} min={d.start}
            onChange={(e) => e.target.value && d.setRange(d.start, e.target.value)} className={cn(inputClass, "w-auto")} />
          <span className="text-xs text-[var(--text-muted)]">Dates are in store time ({tz}).</span>
        </div>
      )}
      {d.data === "all" && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-amber-200/90">
          <Badge tone="warn">Includes non-production data</Badge>
          {["sample", "demo", "legacy_cv"].map((s) => <span key={s}>{SOURCE_LABELS[s]}</span>)}
        </div>
      )}
      {jumpNote && <p className="text-xs text-[var(--text-muted)]">{jumpNote}</p>}
    </div>
  );
}

/** One-line provenance: which sources produced the numbers on the page. */
export function SourceLine({ breakdown }: { breakdown: Record<string, number> | undefined }) {
  if (!breakdown) return null;
  const entries = Object.entries(breakdown).filter(([, n]) => n > 0);
  if (!entries.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs text-[var(--text-muted)]">
      <span>Events in range by source:</span>
      {entries.map(([s, n]) => (
        <Badge key={s} tone={s === "cv" || s === "api" ? "good" : "warn"}>
          {SOURCE_LABELS[s] ?? s}: {n.toLocaleString("en-IN")}
        </Badge>
      ))}
    </div>
  );
}
