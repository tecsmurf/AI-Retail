"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useInterval, useResource } from "@/lib/hooks";
import type { EdgeCamera, EdgeCameraStatus, EdgeDevice, EdgeDeviceList, Store } from "@/lib/types";
import { cn, fmtInt, parseUtc, relativeTime } from "@/lib/utils";
import { Badge, Button, Card, CardTitle, ErrorState, Loading, Note, inputClass } from "./ui";

const CAMERA_STATE: Record<EdgeCameraStatus, { label: string; tone: "good" | "info" | "bad" | "warn" | "neutral" }> = {
  online: { label: "Live", tone: "good" },
  connecting: { label: "Connecting", tone: "info" },
  offline: { label: "Offline", tone: "bad" },
  error: { label: "Error", tone: "bad" },
  unconfigured: { label: "No stream address", tone: "warn" },
  unknown: { label: "Not reported", tone: "neutral" },
};

/**
 * The store's in-store boxes: a small program on a PC in the store that
 * watches the camera streams on site. Status here is what the box itself
 * reported with its last check-in; nothing is assumed.
 */
export function EdgeBoxes({ store, canManage, onCamerasChanged }: {
  store: Store; canManage: boolean; onCamerasChanged?: () => void;
}) {
  const list = useResource(`edge:${store.id}`, (signal) => api<EdgeDeviceList>(`/api/stores/${store.id}/edge-devices`, { signal }));
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  // Pairing codes are returned once, when created; they live only in this page's memory.
  const [codes, setCodes] = useState<Record<string, string>>({});
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const devices = list.data?.items ?? [];
  const anyOnline = devices.some((d) => d.online);

  useInterval(() => {
    list.reload();
    // A box that is live may have just delivered a new still image.
    if (anyOnline) onCamerasChanged?.();
  }, 15000);

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      list.reload();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  const remember = (d: EdgeDevice) => {
    if (d.pairing_code) setCodes((c) => ({ ...c, [d.id]: d.pairing_code as string }));
  };
  const add = () => run(async () => {
    remember(await api<EdgeDevice>(`/api/stores/${store.id}/edge-devices`, { json: { name: name.trim() } }));
    setName("");
    setAdding(false);
  });
  const newCode = (d: EdgeDevice) => {
    if (d.status === "active" && !window.confirm(
      `Create a new pairing code for "${d.name}"? The box that is connected now stops being accepted until it is paired again.`)) return;
    void run(async () => remember(await api<EdgeDevice>(`/api/edge-devices/${d.id}/pairing-code`, { method: "POST" })));
  };
  const remove = (d: EdgeDevice) => {
    if (!window.confirm(`Remove "${d.name}"? It stops sending data at once. Data it already sent is kept.`)) return;
    void run(async () => { await api(`/api/edge-devices/${d.id}/revoke`, { method: "POST" }); });
  };

  return (
    <Card>
      <CardTitle title="Live cameras" hint={store.name}
        action={canManage && !adding && devices.length > 0 ? <Button variant="ghost" onClick={() => setAdding(true)}>Add box</Button> : undefined} />
      {list.error && <ErrorState error={list.error} onRetry={list.reload} />}
      {list.loading && !list.data && <Loading />}
      {list.data && devices.length === 0 && !adding && (
        <div className="space-y-3 text-sm text-[var(--text-secondary)]">
          <p>
            Connect this store&apos;s cameras with a small program on a PC in the store. It watches the camera streams
            on site and sends only anonymous counts. Video and camera passwords stay in the store.
          </p>
          {canManage ? <Button variant="primary" onClick={() => setAdding(true)}>Add a box</Button>
            : <p className="text-xs text-[var(--text-muted)]">An administrator can add a box.</p>}
        </div>
      )}
      {adding && (
        <div className="mb-3 space-y-2">
          <label className="block text-xs font-medium text-[var(--text-secondary)]" htmlFor="edge-name">Name for the box</label>
          <div className="flex gap-2">
            <input id="edge-name" className={cn(inputClass, "flex-1")} placeholder="e.g. Back office PC" value={name}
              maxLength={120} onChange={(e) => setName(e.target.value)} />
            <Button variant="primary" disabled={busy || !name.trim()} onClick={() => void add()}>Add box</Button>
            <Button variant="ghost" onClick={() => setAdding(false)}>Cancel</Button>
          </div>
        </div>
      )}
      {error !== null && <div className="mb-3"><ErrorState error={error} /></div>}
      <ul className="space-y-4">
        {devices.map((d) => (
          <li key={d.id} className="rounded-lg border border-[var(--border-color)] p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="min-w-0 flex-1 truncate text-sm font-medium">{d.name}</span>
              <BoxBadge d={d} />
            </div>
            {d.status === "pending" ? (
              <Pairing d={d} code={codes[d.id]} />
            ) : (
              <>
                <p className="mt-1 text-xs text-[var(--text-muted)]">
                  {d.last_seen_at ? `Last check-in ${relativeTime(d.last_seen_at)}` : "Has not checked in yet"}
                  {d.hostname ? ` · ${d.hostname}` : ""}{d.agent_version ? ` · v${d.agent_version}` : ""}
                </p>
                <p className="text-xs text-[var(--text-muted)]">
                  {fmtInt(d.events_received)} events received{d.last_event_at ? `, latest ${relativeTime(d.last_event_at)}` : ""}
                  {d.stats.queued ? ` · ${fmtInt(d.stats.queued)} waiting on the box to be sent` : ""}
                </p>
                {!!d.stats.dropped && (
                  <div className="mt-2"><Note>The box was offline so long that it had to discard {fmtInt(d.stats.dropped)} of its oldest unsent records.</Note></div>
                )}
                {d.cameras.length === 0
                  ? <p className="mt-2 text-xs text-[var(--text-muted)]">This store has no cameras yet. Add them under Cameras.</p>
                  : (
                    <ul className="mt-2 divide-y divide-[var(--border-color)]">
                      {d.cameras.map((c) => <CameraRow key={c.camera_id} c={c} device={d} canManage={canManage} />)}
                    </ul>
                  )}
              </>
            )}
            {canManage && (
              <div className="mt-2 flex flex-wrap gap-2">
                <Button variant="ghost" disabled={busy} onClick={() => newCode(d)}>
                  {d.status === "pending" ? "New code" : "Replace box"}
                </Button>
                <Button variant="ghost" disabled={busy} onClick={() => remove(d)}>Remove</Button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

function BoxBadge({ d }: { d: EdgeDevice }) {
  if (d.status === "pending") return <Badge tone={d.pairing_expired ? "warn" : "info"}>{d.pairing_expired ? "Code expired" : "Waiting to be paired"}</Badge>;
  return <Badge tone={d.online ? "good" : "bad"}>{d.online ? "Online" : "Offline"}</Badge>;
}

function Pairing({ d, code }: { d: EdgeDevice; code: string | undefined }) {
  if (d.pairing_expired) {
    return <p className="mt-2 text-xs text-[var(--text-secondary)]">The pairing code ran out before it was used. Create a new code.</p>;
  }
  if (!code) {
    return (
      <p className="mt-2 text-xs text-[var(--text-secondary)]">
        Waiting for the box to be paired. The code is shown only once, when it is created. If you no longer have it, create a new code.
      </p>
    );
  }
  return (
    <div className="mt-2 space-y-2 text-xs text-[var(--text-secondary)]">
      <p>Pairing code (works once, until {d.pairing_expires_at ? parseUtc(d.pairing_expires_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : "it runs out"}):</p>
      <p className="select-all rounded-lg bg-black/40 px-3 py-2 text-center font-mono text-lg tracking-widest text-white">{code}</p>
      <p>On the store PC, in the box&apos;s folder, run:</p>
      <pre className="select-all whitespace-pre-wrap break-words rounded-lg bg-black/40 px-3 py-2 font-mono text-[11px] text-white">docker compose run --rm edge pair {code}</pre>
      <p>Then start it with <span className="font-mono">docker compose up -d</span>. This card updates by itself once the box checks in.</p>
    </div>
  );
}

function CameraRow({ c, device, canManage }: { c: EdgeCamera; device: EdgeDevice; canManage: boolean }) {
  const [note, setNote] = useState<string | null>(null);
  const state = CAMERA_STATE[c.status] ?? CAMERA_STATE.unknown;
  async function refreshStill() {
    setNote(null);
    try {
      const r = await api<{ expect_within_seconds: number }>(`/api/edge-devices/${device.id}/snapshot-request/${c.camera_id}`, { method: "POST" });
      setNote(`Asked the box for a new still image. It should arrive within about ${Math.ceil(r.expect_within_seconds / 60)} min.`);
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Could not ask for a still image.");
    }
  }
  const detail = c.status === "online"
    ? [c.width && c.height ? `${c.width}×${c.height}` : "", c.fps ? `${c.fps.toFixed(1)} frames/s analysed` : "",
      c.last_frame_at ? `last frame ${relativeTime(c.last_frame_at)}` : ""].filter(Boolean).join(" · ")
    : c.status === "unconfigured" ? "Add this camera's stream address to the settings file on the box."
      : c.status === "unknown" ? "The box has not reported this camera yet."
        : c.message || (c.last_frame_at ? `Last frame ${relativeTime(c.last_frame_at)}` : "");
  return (
    <li className="py-2">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium">{c.camera_code}</span>
        <span className="min-w-0 flex-1 truncate text-[var(--text-muted)]">{c.name}</span>
        <Badge tone={state.tone}>{state.label}</Badge>
      </div>
      {detail && <p className="mt-0.5 break-words text-xs text-[var(--text-muted)]">{detail}</p>}
      {canManage && c.status === "online" && (
        <button className="mt-1 text-xs text-purple-300 underline" onClick={() => void refreshStill()}>Refresh still image</button>
      )}
      {note && <p className="mt-1 text-xs text-[var(--text-secondary)]">{note}</p>}
    </li>
  );
}
