"use client";

import { Badge, Card, CardTitle, Empty, ErrorState, Loading, Note, PageHeader, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import { useInterval, useResource } from "@/lib/hooks";
import { useSession } from "@/components/session";
import type { AuditEntry, Readiness, SystemStatus } from "@/lib/types";
import { fmtDateTime, fmtDuration, relativeTime } from "@/lib/utils";
import { useState } from "react";

export default function SystemPage() {
  const status = useResource("system-status", (signal) => api<SystemStatus>("/api/system/status", { signal }));
  const ready = useResource("ready", (signal) =>
    fetch("/health/ready", { signal, cache: "no-store" }).then(async (r) => (await r.json()) as Readiness));
  useInterval(() => { status.reload(); ready.reload(); }, 15000);
  const s = status.data;
  const { isAdmin } = useSession();

  return (
    <>
      <PageHeader title="System" subtitle="API, database, storage and video workers" />
      {status.error && <ErrorState error={status.error} onRetry={status.reload} />}
      {!s && !status.error && <Loading />}
      <div className="space-y-4">
        <Card>
          <CardTitle title="Health" hint="Refreshes every 15 seconds" />
          {ready.error && <ErrorState error={ready.error} />}
          {ready.data && (
            <ul className="space-y-2 text-sm">
              {Object.entries(ready.data.checks).map(([k, c]) => (
                <li key={k} className="flex flex-wrap items-center gap-2">
                  <Badge tone={c.ok ? "good" : "bad"}>{c.ok ? "ok" : "problem"}</Badge>
                  <span className="capitalize">{k}</span>
                  <span className="text-xs text-[var(--text-muted)]">
                    {Object.entries(c).filter(([key]) => key !== "ok").map(([key, v]) => `${key}: ${String(v)}`).join(" · ")}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        {s && (
          <>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Stat label="Waiting in queue" value={String(s.queue.queue_depth)}
                sub={s.queue.oldest_queued_age_seconds !== null ? `Oldest waiting ${fmtDuration(s.queue.oldest_queued_age_seconds)}` : undefined} />
              <Stat label="Processing now" value={String(s.queue.running)} />
              <Stat label="Completed (24 h)" value={String(s.queue.finished_last_24h.completed ?? 0)} />
              <Stat label="Failed (24 h)" value={String(s.queue.finished_last_24h.failed ?? 0)} tone={(s.queue.finished_last_24h.failed ?? 0) > 0 ? "warn" : "default"} />
            </div>
            <Card>
              <CardTitle title="Video workers" />
              {s.workers.length === 0 ? (
                <Empty title="No worker has reported in">Uploaded videos stay queued until a worker service is running.</Empty>
              ) : (
                <ul className="divide-y divide-[var(--border-color)] text-sm">
                  {s.workers.map((w) => (
                    <li key={w.worker_id} className="flex flex-wrap items-center gap-2 py-2">
                      <Badge tone={w.online ? "good" : "neutral"}>{w.online ? "online" : "offline"}</Badge>
                      <span className="font-mono text-xs">{w.worker_id}</span>
                      <span className="text-xs text-[var(--text-muted)]">seen {relativeTime(w.last_seen_at)} · {w.device ?? "?"} · model {w.model_loaded ? "loaded" : "not loaded"}</span>
                      {w.busy && w.online && <Badge tone="info">working</Badge>}
                      {w.model_error && <span className="w-full text-xs text-rose-300">{w.model_error}</span>}
                    </li>
                  ))}
                </ul>
              )}
              {s.queue.queue_depth > 0 && !s.workers.some((w) => w.online) && (
                <div className="mt-3"><Note>Jobs are waiting but no worker is online. Check the worker service.</Note></div>
              )}
            </Card>
            <Card>
              <CardTitle title="Configuration" hint={`API ${s.api.version} · ${s.api.env} · up ${fmtDuration(s.api.uptime_seconds)}`} />
              <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                {Object.entries(s.config).map(([k, v]) => (
                  <div key={k}><dt className="text-xs text-[var(--text-muted)]">{k.replace(/_/g, " ")}</dt><dd>{String(v)}</dd></div>
                ))}
              </dl>
            </Card>
          </>
        )}
        {isAdmin && <AuditCard />}
      </div>
    </>
  );
}

const AUDIT_FILTERS: [string, string][] = [
  ["", "Everything"],
  ["auth.", "Sign-ins and passwords"],
  ["user.", "Team changes"],
  ["store.", "Stores"],
  ["camera.", "Cameras and zones"],
  ["region.", "Regions"],
  ["video.", "Uploads"],
  ["job.", "Processing"],
  ["pos.", "POS imports"],
];

function describe(e: AuditEntry): string {
  const d = e.details ?? {};
  const parts = Object.entries(d)
    .filter(([, v]) => v !== null && v !== "" && typeof v !== "object")
    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${String(v)}`);
  return parts.join(" · ");
}

/** Who changed what in this organisation (administrators only). */
function AuditCard() {
  const [action, setAction] = useState("");
  const log = useResource(`audit:${action}`, (signal) =>
    api<{ total: number; items: AuditEntry[] }>("/api/org/audit", { signal, query: { action, limit: 50 } }));
  return (
    <Card>
      <CardTitle title="Activity log" hint="Sign-ins, setup and team changes, uploads. Newest first."
        action={
          <select aria-label="Filter activity" value={action} onChange={(e) => setAction(e.target.value)}
            className="min-h-10 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-2 text-sm">
            {AUDIT_FILTERS.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
          </select>
        } />
      {log.error && <ErrorState error={log.error} onRetry={log.reload} />}
      {log.loading && !log.data && <Loading />}
      {log.data && (log.data.items.length === 0 ? <Empty title="Nothing recorded yet" /> : (
        <ul className="divide-y divide-[var(--border-color)] text-sm">
          {log.data.items.map((e) => (
            <li key={e.id} className="py-2">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="font-mono text-xs text-purple-200">{e.action}</span>
                <span className="text-[var(--text-secondary)]">{e.actor}</span>
                <span className="ml-auto text-xs text-[var(--text-muted)]">{fmtDateTime(e.created_at)}</span>
              </div>
              {describe(e) && <div className="mt-0.5 break-words text-xs text-[var(--text-muted)]">{describe(e)}</div>}
            </li>
          ))}
        </ul>
      ))}
      {log.data && log.data.total > log.data.items.length && (
        <p className="mt-2 text-xs text-[var(--text-muted)]">Showing the latest {log.data.items.length} of {log.data.total}.</p>
      )}
    </Card>
  );
}
