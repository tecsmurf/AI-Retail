"use client";

import { useDashboard } from "@/components/dashboard";
import { FilterBar, SourceLine } from "@/components/filters";
import { Bars, RankBars } from "@/components/charts";
import { Badge, Card, CardTitle, Empty, ErrorState, Loading, Note, PageHeader, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import type { Overview, PosCorrelation } from "@/lib/types";
import { ZONE_COLORS, fmtCurrency, fmtDay, fmtDuration, fmtInt, fmtPercent } from "@/lib/utils";

export default function AnalyticsPage() {
  const d = useDashboard();
  const base = d.store ? `${d.store.id}:${d.start}:${d.end}:${d.data}` : null;
  const ov = useResource(base && `ov:${base}`, (signal) => api<Overview>(`/api/analytics/${d.store!.id}/overview`, { query: d.query, signal }));
  const pos = useResource(base && `pos:${base}`, (signal) => api<PosCorrelation>(`/api/analytics/${d.store!.id}/pos-correlation`, { query: d.query, signal }));
  const defs = useResource("defs", (signal) => api<Record<string, string>>("/api/analytics/definitions", { signal }));

  return (
    <>
      <PageHeader title="Analytics" subtitle="Footfall, zones, queues and sales for the selected range" />
      <FilterBar />
      {d.storesError && <ErrorState error={d.storesError} onRetry={d.reloadStores} />}
      {ov.error && <ErrorState error={ov.error} onRetry={ov.reload} />}
      {ov.loading && !ov.data && <Loading />}
      {ov.data && (
        <div className="space-y-4">
          <SourceLine breakdown={ov.data.source_breakdown} />
          <FootfallSection o={ov.data} />
          <ZonesSection o={ov.data} />
          <QueueSection o={ov.data} />
          <SalesSection o={ov.data} pos={pos.data} posError={pos.error} />
          {defs.data && (
            <Card>
              <details>
                <summary className="cursor-pointer text-sm font-semibold">How each number is defined</summary>
                <dl className="mt-3 space-y-3 text-sm">
                  {Object.entries(defs.data).map(([k, v]) => (
                    <div key={k}><dt className="font-medium">{k.replace(/_/g, " ")}</dt><dd className="text-[var(--text-secondary)]">{v}</dd></div>
                  ))}
                </dl>
              </details>
            </Card>
          )}
        </div>
      )}
    </>
  );
}

function FootfallSection({ o }: { o: Overview }) {
  const ff = o.footfall;
  return (
    <section id="footfall" className="space-y-3">
      <h2 className="text-base font-semibold">Footfall</h2>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Entries" value={fmtInt(ff.entries)} />
        <Stat label="Exits" value={fmtInt(ff.exits)} />
        <Stat label="Avg. entries / day" value={fmtInt(ff.avg_daily_entries)} />
        <Stat label="Busiest hour" value={ff.peak_hour ?? "—"} sub={ff.peak_hour ? `${ff.peak_hour_entries} entries` : undefined} />
      </div>
      {!o.coverage.has_entrance_footage && ff.entries === 0 && (
        <Note>Entries are only counted on entrance cameras that have an entry line. Draw one under Cameras &amp; zones, then process a recording.</Note>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardTitle title="Entries per day" />
          <Bars data={o.footfall.daily.map((x) => ({ ...x, day: fmtDay(x.date) }))} x="day" y="entries" />
        </Card>
        <Card>
          <CardTitle title="Entries by hour of day" hint="Summed over the range, store-local time" />
          <Bars data={ff.hourly} x="label" y="entries" color="#06b6d4" />
        </Card>
      </div>
    </section>
  );
}

function ZonesSection({ o }: { o: Overview }) {
  return (
    <section id="zones" className="space-y-3">
      <h2 className="text-base font-semibold">Zones</h2>
      <Card className="overflow-hidden p-0 sm:p-0">
        {o.zones.length === 0 ? (
          <div className="p-4"><Empty title="No zone visits in this range" /></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead className="text-left text-xs text-[var(--text-muted)]">
                <tr className="border-b border-[var(--border-color)]">
                  <th className="px-4 py-2 font-medium">Zone</th>
                  <th className="px-3 py-2 text-right font-medium">Visits</th>
                  <th className="px-3 py-2 text-right font-medium">People</th>
                  <th className="px-3 py-2 text-right font-medium">Median dwell</th>
                  <th className="px-3 py-2 text-right font-medium">P90 dwell</th>
                  <th className="px-4 py-2 text-right font-medium">Total time</th>
                </tr>
              </thead>
              <tbody>
                {o.zones.map((z) => (
                  <tr key={z.zone_name} className="border-b border-[var(--border-color)] last:border-0">
                    <td className="px-4 py-2.5">
                      <span className="mr-2 inline-block h-2 w-2 rounded-full" style={{ background: ZONE_COLORS[z.zone_type ?? "OTHER"] ?? "#64748b" }} />
                      {z.zone_name}
                      <span className="ml-2 text-xs text-[var(--text-muted)]">{z.cameras.join(", ")}</span>
                    </td>
                    <td className="px-3 text-right tabular-nums">{fmtInt(z.visits)}</td>
                    <td className="px-3 text-right tabular-nums">{fmtInt(z.unique_tracks)}</td>
                    <td className="px-3 text-right tabular-nums">{fmtDuration(z.median_dwell_seconds)}</td>
                    <td className="px-3 text-right tabular-nums">{fmtDuration(z.p90_dwell_seconds)}</td>
                    <td className="px-4 text-right tabular-nums">{fmtDuration(z.total_dwell_seconds)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <Note>&ldquo;People&rdquo; counts distinct anonymous tracks; someone who leaves the camera view and returns may be counted again.</Note>
    </section>
  );
}

function QueueSection({ o }: { o: Overview }) {
  const q = o.queue;
  const hasLength = q.avg_queue_length !== null;
  return (
    <section id="queue" className="space-y-3">
      <h2 className="text-base font-semibold">Queue</h2>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Queue visits" value={fmtInt(q.queue_visits)} />
        <Stat label="Median / P90 wait" value={`${fmtDuration(q.median_wait_seconds)} / ${fmtDuration(q.p90_wait_seconds)}`} />
        <Stat label="Avg. / max queue length" value={hasLength ? `${q.avg_queue_length} / ${q.max_queue_length}` : "—"}
          sub={hasLength ? `Over ${q.observed_queue_hours} h of processed video` : "Needs processed billing-camera footage"} />
        <Stat label="Left queue before counter" value={fmtPercent(q.abandonment_rate)}
          sub={`${q.abandoned} inferred · ${q.completed} reached counter · ${q.outcome_unknown} unknown`} />
      </div>
      {q.current_queue_length !== null && (
        <Badge tone="info">Latest sample: {q.current_queue_length} in queue</Badge>
      )}
      <Note>Waiting time is time spent inside a QUEUE zone. &ldquo;Left before counter&rdquo; is inferred only when the person stayed visible and a counter zone exists on the same camera; if the track was lost the outcome is counted as unknown.</Note>
    </section>
  );
}

function SalesSection({ o, pos, posError }: { o: Overview; pos?: PosCorrelation; posError?: Error }) {
  const rev = o.revenue;
  return (
    <section id="sales" className="space-y-3">
      <h2 className="text-base font-semibold">Sales (POS)</h2>
      {!rev.available ? (
        <Empty title="No POS data linked to this store">{rev.reason} An administrator can import a POS CSV and set the store&apos;s POS code.</Empty>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Revenue" value={fmtCurrency(rev.total_revenue)} />
            <Stat label="Transactions" value={fmtInt(rev.transactions)} sub={`${fmtInt(rev.items)} line items`} />
            <Stat label="Avg. order value" value={fmtCurrency(rev.avg_order_value)} />
            <Stat label="Conversion (est.)" value={fmtPercent(o.conversion.conversion_rate)} sub={o.conversion.notes[0]} />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardTitle title="Top brands by revenue" />
              {rev.top_brands.length ? (
                <RankBars rows={rev.top_brands.map((b) => ({ label: b.brand, value: b.revenue, sub: `${b.items} items` }))}
                  format={(n) => fmtCurrency(n)} color="#10b981" />
              ) : <Empty title="No sales in this range" />}
            </Card>
            <Card>
              <CardTitle title="Orders matched to counter visits" hint="Estimated by time overlap; not an identification" />
              {posError && <ErrorState error={posError} />}
              {pos && (
                <>
                  <dl className="grid grid-cols-3 gap-3 text-sm">
                    <div><dt className="text-xs text-[var(--text-muted)]">Orders</dt><dd className="tabular-nums">{pos.orders}</dd></div>
                    <div><dt className="text-xs text-[var(--text-muted)]">Matched</dt><dd className="tabular-nums">{pos.matched.length}</dd></div>
                    <div><dt className="text-xs text-[var(--text-muted)]">Counter visits</dt><dd className="tabular-nums">{pos.counter_visits}</dd></div>
                  </dl>
                  <div className="mt-3"><Note>{pos.method}</Note></div>
                </>
              )}
            </Card>
          </div>
        </>
      )}
    </section>
  );
}
