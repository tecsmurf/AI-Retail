"use client";

import { useState } from "react";
import { useDashboard } from "@/components/dashboard";
import { FilterBar } from "@/components/filters";
import { useSession } from "@/components/session";
import { Badge, Button, Card, CardTitle, Empty, ErrorState, Loading, Note, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import type { Alert, Anomaly, Insights } from "@/lib/types";
import { fmtDateTime, relativeTime } from "@/lib/utils";

const CONF_TONE = { low: "warn", medium: "info", high: "good" } as const;
const SEV_TONE: Record<string, "bad" | "warn" | "info"> = { high: "bad", critical: "bad", medium: "warn", low: "info" };

export default function InsightsPage() {
  const d = useDashboard();
  const { isAdmin } = useSession();
  const base = d.store ? `${d.store.id}:${d.start}:${d.end}:${d.data}` : null;
  const ins = useResource(base && `ins:${base}`, (signal) => api<Insights>(`/api/analytics/${d.store!.id}/insights`, { query: d.query, signal }));
  const anom = useResource(base && `an:${base}`, (signal) =>
    api<{ items: Anomaly[] }>(`/api/analytics/${d.store!.id}/anomalies`, { query: d.query, signal }));
  const alerts = useResource(d.store ? `al:${d.store.id}` : null, (signal) =>
    api<{ items: Alert[] }>(`/api/analytics/${d.store!.id}/alerts`, { query: { limit: 30 }, signal }));
  const [busy, setBusy] = useState(false);
  const [detectError, setDetectError] = useState<unknown>(null);

  async function detect() {
    if (!d.store) return;
    setBusy(true);
    setDetectError(null);
    try {
      await api(`/api/analytics/${d.store.id}/detect-anomalies`, { method: "POST", query: d.query });
      anom.reload();
      alerts.reload();
    } catch (e) {
      setDetectError(e);
    } finally {
      setBusy(false);
    }
  }

  async function markRead(a: Alert) {
    await api(`/api/analytics/${d.store!.id}/alerts/${a.id}/read`, { method: "POST" });
    alerts.reload();
  }

  async function resolve(a: Anomaly) {
    await api(`/api/analytics/${d.store!.id}/anomalies/${a.id}/resolve`, { method: "POST" });
    anom.reload();
  }

  return (
    <>
      <PageHeader title="Insights" subtitle="Rule-based findings with the numbers behind them" />
      <FilterBar />
      <div className="space-y-4">
        <Card>
          <CardTitle title="Findings" hint={ins.data?.method} />
          {ins.error && <ErrorState error={ins.error} onRetry={ins.reload} />}
          {ins.loading && !ins.data && <Loading />}
          {ins.data && (
            <>
              {ins.data.insights.length === 0 && <Empty title="Not enough data for findings in this range" />}
              <ul className="space-y-3">
                {ins.data.insights.map((i) => (
                  <li key={i.id} className="rounded-xl border border-[var(--border-color)] p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{i.title}</span>
                      <Badge tone={CONF_TONE[i.confidence]}>{i.confidence} confidence</Badge>
                      <Badge>{i.category}</Badge>
                    </div>
                    <p className="mt-1 text-sm text-[var(--text-secondary)]">{i.detail}</p>
                    <p className="mt-2 font-mono text-[11px] text-[var(--text-muted)]">
                      {Object.entries(i.evidence).map(([k, v]) => `${k}=${v}`).join(" · ")}
                    </p>
                  </li>
                ))}
              </ul>
              {ins.data.insufficient_data.length > 0 && (
                <div className="mt-4 space-y-1">
                  {ins.data.insufficient_data.map((g) => <Note key={g}>{g}</Note>)}
                </div>
              )}
            </>
          )}
        </Card>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardTitle title="Anomalies" hint="Long waits, queue build-ups, traffic drops vs. prior weeks"
              action={isAdmin ? <Button onClick={() => void detect()} disabled={busy}>{busy ? "Checking…" : "Check this range"}</Button> : undefined} />
            {detectError !== null && <ErrorState error={detectError} />}
            {anom.error && <ErrorState error={anom.error} onRetry={anom.reload} />}
            {anom.data && (anom.data.items.length === 0 ? <Empty title="No anomalies recorded for this range" /> : (
              <ul className="divide-y divide-[var(--border-color)]">
                {anom.data.items.map((a) => (
                  <li key={a.id} className="py-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={SEV_TONE[a.severity] ?? "info"}>{a.severity}</Badge>
                      <span className="font-medium">{a.anomaly_type.replace(/_/g, " ").toLowerCase()}</span>
                      {a.zone_name && <span className="text-[var(--text-muted)]">{a.zone_name}</span>}
                      <span className="ml-auto text-xs text-[var(--text-muted)]">{fmtDateTime(a.detected_at)}</span>
                    </div>
                    <p className="mt-1 text-[var(--text-secondary)]">{a.description}</p>
                    {!a.is_resolved && isAdmin && <Button variant="ghost" className="mt-1 -ml-3" onClick={() => void resolve(a)}>Mark resolved</Button>}
                    {a.is_resolved && <Badge tone="good">resolved</Badge>}
                  </li>
                ))}
              </ul>
            ))}
          </Card>
          <Card>
            <CardTitle title="Alerts" hint="Processing failures and anomalies" />
            {alerts.error && <ErrorState error={alerts.error} onRetry={alerts.reload} />}
            {alerts.data && (alerts.data.items.length === 0 ? <Empty title="No alerts" /> : (
              <ul className="divide-y divide-[var(--border-color)]">
                {alerts.data.items.map((a) => (
                  <li key={a.id} className="py-3 text-sm">
                    <div className="flex items-center gap-2">
                      {!a.is_read && <span className="h-2 w-2 rounded-full bg-purple-400" aria-label="unread" />}
                      <span className="font-medium">{a.title}</span>
                      <span className="ml-auto text-xs text-[var(--text-muted)]">{relativeTime(a.created_at)}</span>
                    </div>
                    <p className="mt-1 text-[var(--text-secondary)]">{a.message}</p>
                    {!a.is_read && <Button variant="ghost" className="mt-1 -ml-3" onClick={() => void markRead(a)}>Mark read</Button>}
                  </li>
                ))}
              </ul>
            ))}
          </Card>
        </div>
      </div>
    </>
  );
}
