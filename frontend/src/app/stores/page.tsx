"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useDashboard } from "@/components/dashboard";
import { FilterBar } from "@/components/filters";
import { useSession } from "@/components/session";
import { Badge, Card, CardTitle, Empty, ErrorState, Loading, Note, PageHeader, Stat, inputClass } from "@/components/ui";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { OVERVIEW_PATH } from "@/lib/routes";
import type { OrgOverview, OrgRollup, OrgStoreRow, Region } from "@/lib/types";
import { cn, fmtCurrency, fmtDuration, fmtInt, fmtPercent } from "@/lib/utils";

const FLAG_LABELS: Record<OrgStoreRow["flags"][number], { text: string; tone: "warn" | "bad" | "neutral" }> = {
  no_data: { text: "No camera data", tone: "neutral" },
  no_entrance_data: { text: "No entrance camera data", tone: "warn" },
  no_pos_mapping: { text: "POS not mapped", tone: "neutral" },
  open_anomalies: { text: "Open anomalies", tone: "bad" },
};

type SortKey = "name" | "entries" | "conversion_rate" | "revenue" | "avg_queue_wait_seconds";
const SORTS: [SortKey, string][] = [
  ["entries", "Entries"],
  ["conversion_rate", "Conversion"],
  ["revenue", "Revenue"],
  ["avg_queue_wait_seconds", "Queue wait"],
  ["name", "Name"],
];

function sortRows(rows: OrgStoreRow[], key: SortKey): OrgStoreRow[] {
  if (key === "name") return [...rows].sort((a, b) => a.name.localeCompare(b.name));
  // Highest first; stores without a value go last.
  return [...rows].sort((a, b) => (b[key] ?? -Infinity) - (a[key] ?? -Infinity));
}

export default function StoresPage() {
  const d = useDashboard();
  const router = useRouter();
  const { isAdmin } = useSession();
  const [regionId, setRegionId] = useState("");
  const [sort, setSort] = useState<SortKey>("entries");
  const regions = useResource("org-regions", (signal) => api<{ items: Region[] }>("/api/org/regions", { signal }));
  const key = `org-overview:${d.start}:${d.end}:${d.data}:${regionId}`;
  const ov = useResource(key, (signal) =>
    api<OrgOverview>("/api/org/overview", { signal, query: { ...d.query, region_id: regionId || undefined } }));

  function open(storeId: string) {
    d.setStore(storeId);
    router.push(OVERVIEW_PATH);
  }

  const rows = ov.data ? sortRows(ov.data.stores, sort) : [];

  return (
    <>
      <PageHeader title="All stores" subtitle="Every store you can see, side by side for the same dates"
        action={isAdmin ? <Link href="/onboarding" className="text-sm text-purple-300">Set up a store</Link> : undefined} />
      <FilterBar showStore={false} />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {regions.data && regions.data.items.length > 0 && (
          <select aria-label="Region" value={regionId} onChange={(e) => setRegionId(e.target.value)} className={cn(inputClass, "w-auto")}>
            <option value="">All regions</option>
            {regions.data.items.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
        )}
        <select aria-label="Sort by" value={sort} onChange={(e) => setSort(e.target.value as SortKey)} className={cn(inputClass, "w-auto")}>
          {SORTS.map(([k, label]) => <option key={k} value={k}>Sort: {label}</option>)}
        </select>
      </div>
      {ov.error && <ErrorState error={ov.error} onRetry={ov.reload} />}
      {ov.loading && !ov.data && <Loading label="Comparing stores" />}
      {ov.data && (
        ov.data.stores.length === 0 ? <Empty title="No stores to compare">Stores you have access to appear here.</Empty> : (
          <div className="space-y-4">
            <TotalStats total={ov.data.total} />
            {ov.data.regions.length > 1 && <RegionTable regions={ov.data.regions} />}
            <Card>
              <CardTitle title="Stores" hint={`${rows.length} stores · open one for its full dashboard`} />
              <StoreTable rows={rows} onOpen={open} />
              <StoreCards rows={rows} onOpen={open} />
            </Card>
            <div className="space-y-1">{ov.data.notes.map((n) => <Note key={n}>{n}</Note>)}</div>
          </div>
        )
      )}
    </>
  );
}

function TotalStats({ total }: { total: OrgRollup }) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Stat label="Entries" value={fmtInt(total.entries)} sub={`${total.stores_with_data} of ${total.stores} stores have data`} />
      <Stat label="Conversion" value={fmtPercent(total.conversion_rate)} tone={total.conversion_rate === null ? "muted" : "default"}
        sub="POS transactions ÷ entries, stores with both" />
      <Stat label="Revenue" value={fmtCurrency(total.revenue)} tone={total.revenue === null ? "muted" : "default"}
        sub={total.transactions !== null ? `${fmtInt(total.transactions)} transactions` : "No POS data mapped"} />
      <Stat label="Avg queue wait" value={fmtDuration(total.avg_queue_wait_seconds)}
        tone={total.avg_queue_wait_seconds === null ? "muted" : "default"} sub={`${fmtInt(total.queue_visits)} queue visits`} />
    </div>
  );
}

function RegionTable({ regions }: { regions: OrgRollup[] }) {
  return (
    <Card>
      <CardTitle title="By region" />
      <div className="-mx-4 overflow-x-auto px-4">
        <table className="w-full min-w-[520px] text-sm">
          <thead className="text-left text-xs text-[var(--text-muted)]">
            <tr><th className="py-2 font-medium">Region</th><th className="font-medium">Stores</th><th className="text-right font-medium">Entries</th>
              <th className="text-right font-medium">Conversion</th><th className="text-right font-medium">Revenue</th><th className="text-right font-medium">Queue wait</th></tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-color)] tabular-nums">
            {regions.map((r) => (
              <tr key={r.name}>
                <td className="py-2">{r.name}</td>
                <td>{r.stores_with_data}/{r.stores}</td>
                <td className="text-right">{fmtInt(r.entries)}</td>
                <td className="text-right">{fmtPercent(r.conversion_rate)}</td>
                <td className="text-right">{fmtCurrency(r.revenue)}</td>
                <td className="text-right">{fmtDuration(r.avg_queue_wait_seconds)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Flags({ row }: { row: OrgStoreRow }) {
  if (!row.flags.length) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {row.flags.map((f) => (
        <Badge key={f} tone={FLAG_LABELS[f].tone}>
          {FLAG_LABELS[f].text}{f === "open_anomalies" ? ` (${row.open_anomalies})` : ""}
        </Badge>
      ))}
    </div>
  );
}

function StoreTable({ rows, onOpen }: { rows: OrgStoreRow[]; onOpen: (id: string) => void }) {
  return (
    <div className="hidden overflow-x-auto md:block">
      <table className="w-full text-sm">
        <thead className="text-left text-xs text-[var(--text-muted)]">
          <tr>
            <th className="py-2 font-medium">Store</th><th className="font-medium">Region</th>
            <th className="text-right font-medium">Entries</th><th className="text-right font-medium">Per day</th>
            <th className="text-right font-medium">Conversion</th><th className="text-right font-medium">Revenue</th>
            <th className="text-right font-medium">Queue wait</th><th className="text-right font-medium">Abandoned</th>
            <th className="pl-3 font-medium">Notes</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border-color)] tabular-nums">
          {rows.map((r) => (
            <tr key={r.store_id} className="cursor-pointer hover:bg-white/5" onClick={() => onOpen(r.store_id)}>
              <td className="py-2">
                <div className="font-medium">{r.name}</div>
                <div className="text-xs text-[var(--text-muted)]">{r.store_code}{r.city ? ` · ${r.city}` : ""}</div>
              </td>
              <td className="text-[var(--text-secondary)]">{r.region ?? "—"}</td>
              <td className="text-right">{fmtInt(r.entries)}</td>
              <td className="text-right">{fmtInt(r.avg_daily_entries)}</td>
              <td className="text-right">{fmtPercent(r.conversion_rate)}</td>
              <td className="text-right">{fmtCurrency(r.revenue)}</td>
              <td className="text-right">{fmtDuration(r.avg_queue_wait_seconds)}</td>
              <td className="text-right">{fmtPercent(r.abandonment_rate)}</td>
              <td className="pl-3"><Flags row={r} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StoreCards({ rows, onOpen }: { rows: OrgStoreRow[]; onOpen: (id: string) => void }) {
  return (
    <ul className="space-y-2 md:hidden">
      {rows.map((r) => (
        <li key={r.store_id}>
          <button onClick={() => onOpen(r.store_id)} className="w-full rounded-lg border border-[var(--border-color)] p-3 text-left hover:border-[var(--border-hover)]">
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-medium">{r.name}</span>
              <span className="text-xs text-[var(--text-muted)]">{r.region ?? r.store_code}</span>
            </div>
            <dl className="mt-2 grid grid-cols-4 gap-2 text-xs tabular-nums">
              <div><dt className="text-[var(--text-muted)]">Entries</dt><dd className="text-sm">{fmtInt(r.entries)}</dd></div>
              <div><dt className="text-[var(--text-muted)]">Conv.</dt><dd className="text-sm">{fmtPercent(r.conversion_rate)}</dd></div>
              <div><dt className="text-[var(--text-muted)]">Revenue</dt><dd className="text-sm">{fmtCurrency(r.revenue)}</dd></div>
              <div><dt className="text-[var(--text-muted)]">Wait</dt><dd className="text-sm">{fmtDuration(r.avg_queue_wait_seconds)}</dd></div>
            </dl>
            <div className="mt-2"><Flags row={r} /></div>
          </button>
        </li>
      ))}
    </ul>
  );
}
