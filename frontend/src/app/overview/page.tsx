"use client";

import Link from "next/link";
import { useDashboard } from "@/components/dashboard";
import { FilterBar, SourceLine } from "@/components/filters";
import { Bars, RankBars } from "@/components/charts";
import { Card, CardTitle, Empty, ErrorState, Loading, Note, PageHeader, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import type { Overview } from "@/lib/types";
import { fmtCurrency, fmtDuration, fmtInt, fmtPercent } from "@/lib/utils";

export default function OverviewPage() {
  const d = useDashboard();
  const key = d.store ? `overview:${d.store.id}:${d.start}:${d.end}:${d.data}` : null;
  const res = useResource(key, (signal) => api<Overview>(`/api/analytics/${d.store!.id}/overview`, { query: d.query, signal }));

  if (d.storesError) return <ErrorState error={d.storesError} onRetry={d.reloadStores} />;
  if (d.stores && d.stores.length === 0) {
    return (
      <>
        <PageHeader title="Overview" />
        <Empty title="No stores yet">An administrator can add a store and its cameras under <Link className="text-purple-300 underline" href="/setup">Cameras &amp; zones</Link>.</Empty>
      </>
    );
  }

  return (
    <>
      <PageHeader title="Overview" subtitle={d.store ? `${d.store.name}${d.store.city ? ` · ${d.store.city}` : ""}` : undefined} />
      <FilterBar />
      {res.error && <ErrorState error={res.error} onRetry={res.reload} />}
      {res.loading && !res.data && <Loading />}
      {res.data && <OverviewBody o={res.data} />}
    </>
  );
}

function OverviewBody({ o }: { o: Overview }) {
  const { footfall: ff, queue: q, revenue: rev, conversion: conv, coverage } = o;
  const realOnly = o.data.length === 2 && o.data.includes("cv");
  const noFootage = realOnly && coverage.processed_video_seconds === 0 && !o.source_breakdown.api;
  const hours = ff.hourly.filter((h) => h.hour >= 6);

  return (
    <div className="space-y-4">
      {noFootage && (
        <Empty title="No processed footage in this date range">
          Upload a recording under <Link className="text-purple-300 underline" href="/videos">Videos</Link>, or use
          &ldquo;Jump to latest data&rdquo; above. Numbers below are zero because nothing was observed, not because the store was empty.
        </Empty>
      )}

      <Takeaways o={o} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
        <Stat label="Entries" value={fmtInt(ff.entries)}
          sub={coverage.has_entrance_footage ? `${fmtInt(ff.exits)} exits` : "Needs an entrance camera with an entry line"}
          tone={coverage.has_entrance_footage || ff.entries ? "default" : "muted"} />
        <Stat label="Zone visits" value={fmtInt(o.zone_visits)} sub={`${o.zones.length} zones with visits`} />
        <Stat label="Avg. zone dwell" value={fmtDuration(o.avg_zone_dwell_seconds)} sub="Per completed visit" />
        <Stat label="Median queue wait" value={fmtDuration(q.median_wait_seconds)}
          sub={q.queue_visits ? `${fmtInt(q.queue_visits)} queue visits` : "No queue visits observed"} />
        <Stat label="Revenue" value={rev.available ? fmtCurrency(rev.total_revenue) : "—"}
          sub={rev.available ? `${fmtInt(rev.transactions)} transactions` : rev.reason} tone={rev.available ? "default" : "muted"} />
        <Stat label="Conversion (est.)" value={fmtPercent(conv.conversion_rate)} sub={conv.notes[0]}
          tone={conv.conversion_rate === null ? "muted" : "default"} title={conv.basis} />
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardTitle title="Entries by hour" hint={ff.peak_hour ? `Busiest: ${ff.peak_hour} (${ff.peak_hour_entries})` : "Store-local time"} />
          {ff.entries ? <Bars data={hours} x="label" y="entries" /> : <Empty title="No entries in this range" />}
        </Card>
        <Card className="lg:col-span-2">
          <CardTitle title="Top zones" hint="Completed visits · median dwell" action={<Link href="/analytics#zones" className="text-xs text-purple-300">All zones</Link>} />
          {o.zones.length ? (
            <RankBars rows={o.zones.slice(0, 6).map((z) => ({
              label: z.zone_name, value: z.visits, sub: `Median dwell ${fmtDuration(z.median_dwell_seconds)}`,
            }))} />
          ) : <Empty title="No zone visits in this range">Zones are drawn per camera under Cameras &amp; zones.</Empty>}
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardTitle title="Queue" hint="From QUEUE zones on billing cameras" action={<Link href="/analytics#queue" className="text-xs text-purple-300">Details</Link>} />
          {q.queue_visits || q.completed || q.abandoned ? (
            <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <div><dt className="text-xs text-[var(--text-muted)]">P90 wait</dt><dd className="tabular-nums">{fmtDuration(q.p90_wait_seconds)}</dd></div>
              <div><dt className="text-xs text-[var(--text-muted)]">Reached counter</dt><dd className="tabular-nums">{fmtInt(q.completed)}</dd></div>
              <div><dt className="text-xs text-[var(--text-muted)]">Left queue (inferred)</dt><dd className="tabular-nums">{fmtInt(q.abandoned)}</dd></div>
              <div><dt className="text-xs text-[var(--text-muted)]">Outcome unknown</dt><dd className="tabular-nums">{fmtInt(q.outcome_unknown)}</dd></div>
            </dl>
          ) : <Empty title="No queue activity observed" />}
        </Card>
        <Card>
          <CardTitle title="Footage behind these numbers" hint={`${fmtDuration(coverage.processed_video_seconds)} of processed video in range`} />
          {Object.keys(coverage.cameras).length ? (
            <ul className="divide-y divide-[var(--border-color)] text-sm">
              {Object.entries(coverage.cameras).map(([code, c]) => (
                <li key={code} className="flex justify-between py-2">
                  <span>{code} <span className="text-xs capitalize text-[var(--text-muted)]">{c.camera_type}</span></span>
                  <span className="tabular-nums text-[var(--text-secondary)]">{c.videos} video{c.videos === 1 ? "" : "s"} · {fmtDuration(c.seconds)}</span>
                </li>
              ))}
            </ul>
          ) : <Note>No processed video overlaps this range.</Note>}
          <div className="mt-3"><SourceLine breakdown={o.source_breakdown} /></div>
        </Card>
      </div>
    </div>
  );
}

/**
 * The same numbers as the tiles below, said in plain words so a store manager
 * can see what they mean at a glance. Only facts present in the data are shown.
 */
function Takeaways({ o }: { o: Overview }) {
  const lines: string[] = [];
  const ff = o.footfall;
  if (ff.entries && ff.peak_hour) {
    lines.push(`${fmtInt(ff.entries)} ${ff.entries === 1 ? "person" : "people"} came in. The busiest hour was ${ff.peak_hour}, with ${fmtInt(ff.peak_hour_entries)} entries.`);
  }
  if (o.conversion.conversion_rate !== null) {
    lines.push(`${fmtPercent(o.conversion.conversion_rate)} of visitors bought something (bills ÷ entries, estimated).`);
  }
  const top = o.zones[0];
  if (top && top.visits) {
    const stay = top.median_dwell_seconds !== null ? `, with a median stay of ${fmtDuration(top.median_dwell_seconds)}` : "";
    lines.push(`${top.zone_name} drew the most visits (${fmtInt(top.visits)})${stay}.`);
  }
  if (o.queue.queue_visits && o.queue.median_wait_seconds !== null) {
    lines.push(`At billing, half of shoppers waited under ${fmtDuration(o.queue.median_wait_seconds)}${o.queue.p90_wait_seconds !== null && o.queue.queue_visits >= 10 ? ` and 1 in 10 waited over ${fmtDuration(o.queue.p90_wait_seconds)}` : ""}.`);
  }
  if (!lines.length) return null;
  return (
    <Card className="border-purple-500/30 bg-gradient-to-br from-purple-500/[0.08] to-transparent">
      <CardTitle title="What this means" hint="Plain-language summary of the numbers below" />
      <ul className="space-y-1.5 text-sm leading-relaxed text-[var(--text-secondary)]">
        {lines.map((l) => (
          <li key={l} className="flex gap-2"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-purple-400" />{l}</li>
        ))}
      </ul>
    </Card>
  );
}
