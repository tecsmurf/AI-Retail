"use client";

import { Badge, Card, CardTitle, Empty, ErrorState, Loading, Note, PageHeader, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import { useInterval, useResource } from "@/lib/hooks";
import type { Readiness, SystemStatus } from "@/lib/types";
import { fmtDuration, relativeTime } from "@/lib/utils";

export default function SystemPage() {
  const status = useResource("system-status", (signal) => api<SystemStatus>("/api/system/status", { signal }));
  const ready = useResource("ready", (signal) =>
    fetch("/health/ready", { signal, cache: "no-store" }).then(async (r) => (await r.json()) as Readiness));
  useInterval(() => { status.reload(); ready.reload(); }, 15000);
  const s = status.data;

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
                      {w.current_job_id && w.online && <Badge tone="info">working</Badge>}
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
      </div>
    </>
  );
}
