"use client";

import Link from "next/link";
import { useState } from "react";
import { CheckCircle2, Circle } from "lucide-react";
import { useDashboard } from "@/components/dashboard";
import { EdgeBoxes } from "@/components/edge-boxes";
import { useSession } from "@/components/session";
import { Badge, Button, Card, CardTitle, ErrorState, Field, Loading, Note, PageHeader, inputClass } from "@/components/ui";
import { api } from "@/lib/api";
import { useInterval, useResource } from "@/lib/hooks";
import { OVERVIEW_PATH } from "@/lib/routes";
import type { CameraType, Region, SetupStatus, SetupStep, Store } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Guided setup: new store -> cameras -> in-store box -> zones -> first data. */
export default function OnboardingPage() {
  const d = useDashboard();
  const { isAdmin } = useSession();
  const [creating, setCreating] = useState(false);

  if (!isAdmin) {
    return (
      <>
        <PageHeader title="Set up a store" />
        <Note>Only HQ admins can set up stores. You can see each store&apos;s cameras under Cameras &amp; zones.</Note>
      </>
    );
  }
  const store = creating ? undefined : d.store;

  return (
    <>
      <PageHeader title="Set up a store" subtitle="From a new store to live numbers, one step at a time"
        action={!creating ? <Button onClick={() => setCreating(true)}>New store</Button> : undefined} />
      {creating || !d.stores?.length ? (
        <NewStore onCreated={(s) => { d.reloadStores(); d.setStore(s.id); setCreating(false); }}
          onCancel={d.stores?.length ? () => setCreating(false) : undefined} />
      ) : store ? (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
            <span className="text-[var(--text-secondary)]">Store</span>
            <select aria-label="Store" className={cn(inputClass, "w-auto")} value={store.id} onChange={(e) => d.setStore(e.target.value)}>
              {d.stores?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <Checklist key={store.id} store={store} />
        </>
      ) : <Loading />}
    </>
  );
}

function NewStore({ onCreated, onCancel }: { onCreated: (s: Store) => void; onCancel?: () => void }) {
  const regions = useResource("org-regions", (signal) => api<{ items: Region[] }>("/api/org/regions", { signal }));
  const [form, setForm] = useState({ store_code: "", name: "", city: "", timezone: "Asia/Kolkata", region_id: "", pos_store_code: "" });
  const [error, setError] = useState<unknown>(null);
  async function create() {
    setError(null);
    try {
      onCreated(await api<Store>("/api/stores", {
        json: { ...form, city: form.city || null, region_id: form.region_id || null, pos_store_code: form.pos_store_code || null },
      }));
    } catch (e) {
      setError(e);
    }
  }
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [k]: e.target.value });
  return (
    <Card>
      <CardTitle title="1. Store details" hint="You can change all of these later." />
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Store name"><input className={inputClass} value={form.name} onChange={set("name")} placeholder="DMart Powai" /></Field>
        <Field label="Store code" hint="Short and unique, e.g. MUM-POWAI"><input className={inputClass} value={form.store_code} onChange={set("store_code")} /></Field>
        <Field label="City"><input className={inputClass} value={form.city} onChange={set("city")} /></Field>
        <Field label="Time zone" hint="IANA name"><input className={inputClass} value={form.timezone} onChange={set("timezone")} /></Field>
        {regions.data && regions.data.items.length > 0 && (
          <Field label="Region">
            <select className={inputClass} value={form.region_id} onChange={set("region_id")}>
              <option value="">No region</option>
              {regions.data.items.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          </Field>
        )}
        <Field label="POS store code (optional)" hint="The store id used in your POS export">
          <input className={inputClass} value={form.pos_store_code} onChange={set("pos_store_code")} />
        </Field>
      </div>
      {error !== null && <div className="mt-3"><ErrorState error={error} /></div>}
      <div className="mt-4 flex gap-2">
        <Button variant="primary" disabled={!form.name || !form.store_code} onClick={() => void create()}>Create store</Button>
        {onCancel && <Button variant="ghost" onClick={onCancel}>Cancel</Button>}
      </div>
    </Card>
  );
}

function Checklist({ store }: { store: Store }) {
  const status = useResource(`setup:${store.id}`, (signal) => api<SetupStatus>(`/api/stores/${store.id}/setup-status`, { signal }));
  useInterval(status.reload, 10000);
  const s = status.data;
  if (status.error) return <ErrorState error={status.error} onRetry={status.reload} />;
  if (!s) return <Loading />;
  const step = (k: SetupStep["key"]) => s.steps.find((x) => x.key === k)!;

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          {s.ready ? <Badge tone="good">Ready</Badge> : <Badge tone="warn">Setup in progress</Badge>}
          <span className="text-sm text-[var(--text-secondary)]">{s.done} of {s.total} steps done</span>
          {s.ready && <Link href={OVERVIEW_PATH} className="ml-auto text-sm text-purple-300">Open the dashboard</Link>}
        </div>
        <ol className="mt-3 space-y-1.5 text-sm">
          {s.steps.map((x) => (
            <li key={x.key} className="flex items-start gap-2">
              {x.done ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" /> : <Circle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--text-muted)]" />}
              <span>
                {x.title}{!x.required && <span className="text-[var(--text-muted)]"> (optional)</span>}
                <span className="block text-xs text-[var(--text-muted)]">{x.detail}</span>
              </span>
            </li>
          ))}
        </ol>
      </Card>

      <Card>
        <CardTitle title="2. Cameras" hint="Add every camera you want analysed. Entrance cameras count people coming in." />
        {s.cameras.length > 0 && (
          <ul className="mb-3 divide-y divide-[var(--border-color)] text-sm">
            {s.cameras.map((c) => (
              <li key={c.camera_id} className="flex flex-wrap items-center gap-2 py-2">
                <span className="font-medium">{c.camera_code}</span>
                <span className="text-[var(--text-muted)]">{c.name}</span>
                <Badge>{c.camera_type}</Badge>
                {c.live && <Badge tone="good">Live</Badge>}
                {c.needs.length > 0 && <span className="text-xs text-amber-300">Needs {c.needs.join(", ")}</span>}
              </li>
            ))}
          </ul>
        )}
        <QuickAddCamera storeId={store.id} existing={s.cameras.map((c) => c.camera_code)} onAdded={status.reload} />
      </Card>

      <div>
        <h2 className="mb-2 text-sm font-semibold">3. In-store box</h2>
        <EdgeBoxes store={store} canManage onCamerasChanged={status.reload} />
        {s.boxes === 0 && (
          <div className="mt-2"><Note>No box yet? Upload recordings under <Link className="underline" href="/videos">Videos</Link> to try the store first.</Note></div>
        )}
      </div>

      <Card>
        <CardTitle title="4. Zones and entry line" hint="Draw on a real view of each camera. The still image arrives by itself once the camera is live." />
        {s.cameras.length === 0 ? <Note>Add cameras first.</Note> : (
          <ul className="divide-y divide-[var(--border-color)] text-sm">
            {s.cameras.map((c) => {
              const ready = c.needs.length === 0;
              return (
                <li key={c.camera_id} className="flex flex-wrap items-center gap-2 py-2">
                  {ready ? <CheckCircle2 className="h-4 w-4 text-emerald-400" /> : <Circle className="h-4 w-4 text-[var(--text-muted)]" />}
                  <span className="font-medium">{c.camera_code}</span>
                  <span className="text-xs text-[var(--text-muted)]">
                    {c.camera_type === "entrance" ? (c.has_entry_line ? "entry line drawn" : "draw the entry line where feet cross the door")
                      : c.needs.length ? `needs ${c.needs.join(", ")}` : `${c.zones} zone${c.zones === 1 ? "" : "s"}`}
                    {c.has_still_image ? "" : " · no still image yet"}
                  </span>
                  <Link href={`/setup#camera=${c.camera_id}`} className="ml-auto text-xs text-purple-300">{ready ? "Edit" : "Draw"}</Link>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      <Card>
        <CardTitle title="5. Check the numbers" />
        <p className="text-sm text-[var(--text-secondary)]">{step("data").detail}</p>
        <p className="mt-2 text-xs text-[var(--text-muted)]">
          Before you rely on the counts, compare one busy hour on the dashboard with a manual count from the recording.
          Check that the entry line sits where feet cross it, and that queue zones cover where people stand.
        </p>
        <div className="mt-3 flex flex-wrap gap-2 text-sm">
          <Link href={OVERVIEW_PATH} className="text-purple-300">Overview</Link>
          <span className="text-[var(--text-muted)]">·</span>
          <Link href="/setup" className="text-purple-300">POS mapping and store settings</Link>
        </div>
      </Card>
    </div>
  );
}

function QuickAddCamera({ storeId, existing, onAdded }: { storeId: string; existing: string[]; onAdded: () => void }) {
  const next = `CAM${existing.length + 1}`;
  const [form, setForm] = useState<{ camera_code: string; name: string; camera_type: CameraType }>({ camera_code: "", name: "", camera_type: "entrance" });
  const [error, setError] = useState<unknown>(null);
  async function add() {
    setError(null);
    try {
      await api(`/api/stores/${storeId}/cameras`, { json: { ...form, camera_code: form.camera_code || next } });
      setForm({ camera_code: "", name: "", camera_type: "zone" });
      onAdded();
    } catch (e) {
      setError(e);
    }
  }
  return (
    <div className="grid gap-2 sm:grid-cols-[8rem_1fr_9rem_auto] sm:items-end">
      <Field label="Code"><input className={inputClass} value={form.camera_code} placeholder={next} onChange={(e) => setForm({ ...form, camera_code: e.target.value })} /></Field>
      <Field label="Where it points"><input className={inputClass} value={form.name} placeholder="Main door" onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
      <Field label="Type">
        <select className={inputClass} value={form.camera_type} onChange={(e) => setForm({ ...form, camera_type: e.target.value as CameraType })}>
          <option value="entrance">Entrance</option>
          <option value="zone">Shop floor</option>
          <option value="billing">Billing</option>
          <option value="other">Other</option>
        </select>
      </Field>
      <Button variant="primary" disabled={!form.name} onClick={() => void add()}>Add camera</Button>
      {error !== null && <div className="sm:col-span-4"><ErrorState error={error} /></div>}
    </div>
  );
}
