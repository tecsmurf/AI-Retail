"use client";

import { useState } from "react";
import { useDashboard } from "@/components/dashboard";
import { FilterBar } from "@/components/filters";
import { RankBars } from "@/components/charts";
import { Badge, Button, Card, CardTitle, Empty, ErrorState, Loading, Note, PageHeader, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import type { Journey, JourneyAnalytics, JourneyPage } from "@/lib/types";
import { SOURCE_LABELS, fmtDuration, fmtInt, fmtTime } from "@/lib/utils";

const TYPE_LABELS: Record<string, string> = {
  billing_visit: "Reached counter",
  browse: "Browsed zones",
  bounce: "Entered and left",
  entry_only: "Entry only",
  exit_only: "Exit only",
  other: "Other",
};
const PAGE = 25;

export default function JourneysPage() {
  const d = useDashboard();
  const [type, setType] = useState("");
  const [offset, setOffset] = useState(0);
  const base = d.store ? `${d.store.id}:${d.start}:${d.end}:${d.data}` : null;
  const ja = useResource(base && `ja:${base}`, (signal) =>
    api<JourneyAnalytics>(`/api/analytics/${d.store!.id}/journeys/analytics`, { query: d.query, signal }));
  const list = useResource(base && `jl:${base}:${type}:${offset}`, (signal) =>
    api<JourneyPage>(`/api/analytics/${d.store!.id}/journeys`, {
      query: { ...d.query, journey_type: type || undefined, limit: PAGE, offset }, signal,
    }));

  return (
    <>
      <PageHeader title="Journeys" subtitle="Anonymous paths of tracked people, per camera" />
      <FilterBar />
      {ja.error && <ErrorState error={ja.error} onRetry={ja.reload} />}
      {ja.loading && !ja.data && <Loading />}
      {ja.data && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Journeys" value={fmtInt(ja.data.total_journeys)} />
            <Stat label="Avg. duration" value={fmtDuration(ja.data.avg_duration_seconds)} />
            <Stat label="Avg. zones visited" value={ja.data.avg_zones_visited?.toFixed(1) ?? "—"} />
            <Stat label="Seen entering / exiting" value={`${fmtInt(ja.data.with_observed_entry)} / ${fmtInt(ja.data.with_observed_exit)}`} />
          </div>
          <Note>{ja.data.scope_note} A journey is one track on one camera, so a shopper seen by two cameras appears twice. Purchases are never inferred from visiting the counter.</Note>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardTitle title="Journey types" />
              {ja.data.total_journeys ? (
                <RankBars rows={Object.entries(ja.data.by_type).map(([k, v]) => ({ label: TYPE_LABELS[k] ?? k, value: v }))} />
              ) : <Empty title="No journeys in this range" />}
            </Card>
            <Card>
              <CardTitle title="Most common zone paths" hint="Repeated visits to the same zone are collapsed" />
              {ja.data.top_paths.length ? (
                <ul className="space-y-2 text-sm">
                  {ja.data.top_paths.map((p) => (
                    <li key={p.path.join(">")} className="flex items-start justify-between gap-3">
                      <span className="text-[var(--text-secondary)]">{p.path.join(" → ")}</span>
                      <span className="shrink-0 tabular-nums">{p.count}×</span>
                    </li>
                  ))}
                </ul>
              ) : <Empty title="No multi-zone paths yet" />}
            </Card>
          </div>
        </div>
      )}

      <div className="mt-6 mb-3 flex flex-wrap items-center gap-2">
        <h2 className="mr-auto text-base font-semibold">Individual journeys</h2>
        <select aria-label="Journey type" value={type} onChange={(e) => { setType(e.target.value); setOffset(0); }}
          className="min-h-10 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 text-sm">
          <option value="">All types</option>
          {Object.entries(TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      {list.error && <ErrorState error={list.error} onRetry={list.reload} />}
      {list.loading && !list.data && <Loading />}
      {list.data && (
        list.data.items.length === 0 ? <Empty title="No journeys match" /> : (
          <>
            <ul className="space-y-2">
              {list.data.items.map((j) => <JourneyRow key={j.id} j={j} tz={list.data!.range.timezone} />)}
            </ul>
            <div className="mt-3 flex items-center justify-between text-sm text-[var(--text-muted)]">
              <span>{offset + 1}–{offset + list.data.items.length} of {list.data.total}</span>
              <div className="flex gap-2">
                <Button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</Button>
                <Button disabled={offset + PAGE >= list.data.total} onClick={() => setOffset(offset + PAGE)}>Next</Button>
              </div>
            </div>
          </>
        )
      )}
    </>
  );
}

function JourneyRow({ j, tz }: { j: Journey; tz: string }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="card">
      <button className="flex w-full flex-wrap items-center gap-2 p-3 text-left" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span className="font-mono text-xs text-[var(--text-secondary)]">{j.customer_id}</span>
        <Badge>{TYPE_LABELS[j.journey_type] ?? j.journey_type}</Badge>
        {j.source !== "cv" && <Badge tone="warn">{SOURCE_LABELS[j.source] ?? j.source}</Badge>}
        <span className="ml-auto text-xs tabular-nums text-[var(--text-muted)]">
          {fmtTime(j.entry_time, tz)} · {fmtDuration(j.duration_seconds)} · {j.zone_count} zones
        </span>
      </button>
      {open && (
        <ol className="border-t border-[var(--border-color)] px-3 py-2 text-sm">
          {j.steps.map((s) => (
            <li key={s.sequence} className="flex gap-3 py-1">
              <span className="w-20 shrink-0 tabular-nums text-xs text-[var(--text-muted)]">{fmtTime(s.timestamp, tz)}</span>
              <span>{s.event_type.replace(/_/g, " ").toLowerCase()}{s.zone_name ? ` · ${s.zone_name}` : ""}</span>
              {s.dwell_seconds !== null && <span className="ml-auto text-xs text-[var(--text-muted)]">{fmtDuration(s.dwell_seconds)}</span>}
            </li>
          ))}
        </ol>
      )}
    </li>
  );
}
