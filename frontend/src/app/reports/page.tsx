"use client";

import { Download, Printer } from "lucide-react";
import { useDashboard } from "@/components/dashboard";
import { FilterBar } from "@/components/filters";
import { useSession } from "@/components/session";
import { Button, Card, CardTitle, ErrorState, Loading, Note, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import type { Overview } from "@/lib/types";
import { SOURCE_LABELS, fmtCurrency, fmtDay, fmtDuration, fmtInt, fmtPercent } from "@/lib/utils";

function qs(q: Record<string, string>) {
  return new URLSearchParams(q).toString();
}

function DownloadLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a href={href} download
      className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-[var(--border-color)] bg-[var(--bg-elevated)] px-3 text-sm font-medium transition-colors hover:border-[var(--border-hover)]">
      <Download className="h-4 w-4" /> {children}
    </a>
  );
}

export default function ReportsPage() {
  const d = useDashboard();
  const { user } = useSession();
  const store = d.store;
  const query = { start: d.start, end: d.end, data: d.data };
  const multi = !!user && (user.all_stores || user.store_ids.length > 1);
  const res = useResource(store ? `report:${store.id}:${d.start}:${d.end}:${d.data}` : null,
    (signal) => api<Overview>(`/api/analytics/${store!.id}/overview`, { query, signal }));

  return (
    <>
      <div className="print:hidden">
        <PageHeader title="Reports" subtitle="Download the numbers, or print a one-page summary" />
        <FilterBar />
        <Card className="mb-4">
          <CardTitle title="Downloads (CSV)" hint="Opens in Excel or Google Sheets. Empty cells mean not measured, not zero." />
          <div className="flex flex-wrap gap-2">
            {multi && (
              <DownloadLink href={`/api/reports/stores.csv?${qs(query)}`}>All stores side by side</DownloadLink>
            )}
            {store && (
              <>
                <DownloadLink href={`/api/reports/${store.id}/daily.csv?${qs(query)}`}>{store.name}: day by day</DownloadLink>
                <DownloadLink href={`/api/reports/${store.id}/zones.csv?${qs(query)}`}>{store.name}: zones</DownloadLink>
              </>
            )}
          </div>
          <div className="mt-3"><Note>Day-by-day export covers up to 92 days. Scheduled email reports need an email service to be connected first.</Note></div>
        </Card>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Printable summary</h2>
          <Button variant="primary" onClick={() => window.print()} disabled={!res.data}><Printer className="h-4 w-4" /> Print or save as PDF</Button>
        </div>
      </div>
      {res.error && <ErrorState error={res.error} onRetry={res.reload} />}
      {res.loading && !res.data && <Loading />}
      {res.data && store && <Summary o={res.data} storeName={store.name} city={store.city} />}
    </>
  );
}

function Row({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <tr className="border-b border-[var(--border-color)] print:border-gray-300">
      <td className="py-1.5 pr-4 text-[var(--text-secondary)] print:text-gray-600">{label}</td>
      <td className="py-1.5 pr-4 text-right font-medium tabular-nums">{value}</td>
      <td className="py-1.5 text-xs text-[var(--text-muted)] print:text-gray-500">{note}</td>
    </tr>
  );
}

function Summary({ o, storeName, city }: { o: Overview; storeName: string; city: string | null }) {
  const { footfall: ff, queue: q, revenue: rev, conversion: conv, coverage: cov } = o;
  const sources = o.data.map((s) => SOURCE_LABELS[s] ?? s).join(", ");
  const footage = [cov.processed_video_seconds ? `${fmtDuration(cov.processed_video_seconds)} of uploaded video` : null,
    cov.live_seconds ? `${fmtDuration(cov.live_seconds)} of live cameras` : null].filter(Boolean).join(" and ") || "no analysed footage";
  const days = ff.daily.filter((x) => x.entries || x.exits);
  return (
    <article className="card p-5 print:border-0 print:bg-white print:p-0 print:text-black">
      <header className="mb-4 border-b border-[var(--border-color)] pb-3 print:border-gray-300">
        <div className="text-xs uppercase tracking-wide text-[var(--text-muted)] print:text-gray-500">PurpleSol store report</div>
        <h1 className="text-xl font-semibold">{storeName}{city ? `, ${city}` : ""}</h1>
        <p className="text-sm text-[var(--text-secondary)] print:text-gray-700">
          {o.range.start === o.range.end ? fmtDay(o.range.start) : `${fmtDay(o.range.start)} to ${fmtDay(o.range.end)}`} · store time ({o.range.timezone})
        </p>
        <p className="mt-1 text-xs text-[var(--text-muted)] print:text-gray-500">Based on {footage}. Data: {sources}.</p>
      </header>

      <table className="w-full text-sm">
        <tbody>
          <Row label="Entries" value={fmtInt(ff.entries)} note={ff.peak_hour ? `Busiest hour ${ff.peak_hour}` : undefined} />
          <Row label="Average per day" value={fmtInt(ff.avg_daily_entries)} />
          <Row label="Zone visits" value={fmtInt(o.zone_visits)} note={`Average dwell ${fmtDuration(o.avg_zone_dwell_seconds)}`} />
          <Row label="Queue visits" value={fmtInt(q.queue_visits)} note={`Median wait ${fmtDuration(q.median_wait_seconds)}, P90 ${fmtDuration(q.p90_wait_seconds)}`} />
          <Row label="Left the queue before the counter" value={fmtPercent(q.abandonment_rate)} note="Inferred from movement" />
          <Row label="Revenue" value={rev.available ? fmtCurrency(rev.total_revenue) : "Not measured"}
            note={rev.available ? `${fmtInt(rev.transactions)} transactions` : rev.reason} />
          <Row label="Conversion (estimate)" value={fmtPercent(conv.conversion_rate)} note={conv.notes[0]} />
        </tbody>
      </table>

      {o.zones.length > 0 && (
        <section className="mt-5 break-inside-avoid">
          <h2 className="mb-1 text-sm font-semibold">Zones</h2>
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-[var(--text-muted)] print:text-gray-500">
              <tr><th className="py-1 font-medium">Zone</th><th className="text-right font-medium">Visits</th><th className="text-right font-medium">Median dwell</th></tr>
            </thead>
            <tbody>
              {o.zones.slice(0, 12).map((z) => (
                <tr key={z.zone_name} className="border-b border-[var(--border-color)] print:border-gray-300">
                  <td className="py-1.5">{z.zone_name}</td>
                  <td className="text-right tabular-nums">{fmtInt(z.visits)}</td>
                  <td className="text-right tabular-nums">{fmtDuration(z.median_dwell_seconds)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {days.length > 1 && (
        <section className="mt-5 break-inside-avoid">
          <h2 className="mb-1 text-sm font-semibold">Entries by day</h2>
          <table className="w-full text-sm">
            <tbody>
              {days.map((x) => (
                <tr key={x.date} className="border-b border-[var(--border-color)] print:border-gray-300">
                  <td className="py-1">{fmtDay(x.date)}</td>
                  <td className="text-right tabular-nums">{fmtInt(x.entries)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <footer className="mt-5 text-xs leading-relaxed text-[var(--text-muted)] print:text-gray-500">
        Counts come from anonymous tracking of people on CCTV; no faces are recognised and no one is identified.
        Conversion is POS transactions divided by entries and is an estimate. Definitions: docs/METRICS.md.
      </footer>
    </article>
  );
}
