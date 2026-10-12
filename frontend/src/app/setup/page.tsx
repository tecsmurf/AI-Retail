"use client";

import { useState } from "react";
import { useDashboard } from "@/components/dashboard";
import { useSession } from "@/components/session";
import { ZoneEditor } from "@/components/zone-editor";
import { Badge, Button, Card, CardTitle, Empty, ErrorState, Field, Loading, Note, PageHeader, inputClass } from "@/components/ui";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import type { Camera, CameraType, Store } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function SetupPage() {
  const d = useDashboard();
  const { isAdmin } = useSession();
  const store = d.store;
  const cams = useResource(store ? `setup-cams:${store.id}` : null, (signal) => api<Camera[]>(`/api/stores/${store!.id}/cameras`, { signal }));
  const [cameraId, setCameraId] = useState<string | null>(null);
  const camera = cams.data?.find((c) => c.id === cameraId) ?? cams.data?.[0];

  return (
    <>
      <PageHeader title="Cameras & zones" subtitle="Stores, cameras, zones, entry lines and POS mapping" />
      {d.storesError && <ErrorState error={d.storesError} onRetry={d.reloadStores} />}
      {!isAdmin && <div className="mb-4"><Note>You can view the configuration; only administrators can change it.</Note></div>}
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="min-w-0 space-y-4">
          <StoresCard />
          {store && isAdmin && <StoreSettings key={store.id} store={store} onSaved={d.reloadStores} />}
          {store && (
            <Card>
              <CardTitle title="Cameras" hint={store.name} />
              {cams.error && <ErrorState error={cams.error} onRetry={cams.reload} />}
              {cams.loading && !cams.data && <Loading />}
              {cams.data && (cams.data.length === 0 ? <Empty title="No cameras yet" /> : (
                <ul className="space-y-1">
                  {cams.data.map((c) => (
                    <li key={c.id}>
                      <button onClick={() => setCameraId(c.id)}
                        className={cn("flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-white/5",
                          camera?.id === c.id && "bg-purple-500/10")}>
                        <span className="font-medium">{c.camera_code}</span>
                        <span className="truncate text-[var(--text-muted)]">{c.name}</span>
                        <Badge>{c.camera_type}</Badge>
                      </button>
                    </li>
                  ))}
                </ul>
              ))}
              {isAdmin && <AddCamera storeId={store.id} onAdded={(c) => { cams.reload(); setCameraId(c.id); }} />}
            </Card>
          )}
        </div>
        <div className="min-w-0 lg:col-span-2">
          {camera ? (
            <Card>
              <CardTitle title={`${camera.camera_code} · ${camera.name}`}
                hint={`${camera.camera_type} camera · configuration v${camera.config_version}${camera.resolution_width ? ` · ${camera.resolution_width}×${camera.resolution_height}` : ""}`} />
              {isAdmin ? <ZoneEditor key={camera.id} camera={camera} onSaved={() => cams.reload()} />
                : <Note>Sign in as an administrator to edit zones.</Note>}
            </Card>
          ) : store && cams.data ? <Empty title="Select or add a camera to draw its zones" /> : null}
        </div>
      </div>
    </>
  );
}

function StoresCard() {
  const d = useDashboard();
  const { isAdmin } = useSession();
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ store_code: "", name: "", city: "", timezone: "Asia/Kolkata" });
  const [error, setError] = useState<unknown>(null);
  async function create() {
    setError(null);
    try {
      const s = await api<Store>("/api/stores", { json: { ...form, city: form.city || null } });
      d.reloadStores();
      d.setStore(s.id);
      setAdding(false);
    } catch (e) {
      setError(e);
    }
  }
  return (
    <Card>
      <CardTitle title="Stores" action={isAdmin && !adding ? <Button variant="ghost" onClick={() => setAdding(true)}>Add</Button> : undefined} />
      {d.stores && (
        <ul className="space-y-1">
          {d.stores.map((s) => (
            <li key={s.id}>
              <button onClick={() => d.setStore(s.id)}
                className={cn("w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-white/5", d.store?.id === s.id && "bg-purple-500/10")}>
                <div className="font-medium">{s.name}</div>
                <div className="text-xs text-[var(--text-muted)]">{s.store_code} · {s.camera_count} cameras · {s.timezone}</div>
              </button>
            </li>
          ))}
        </ul>
      )}
      {adding && (
        <div className="mt-3 space-y-2">
          <Field label="Code" hint="Letters, digits, - _ ."><input className={inputClass} value={form.store_code} onChange={(e) => setForm({ ...form, store_code: e.target.value })} /></Field>
          <Field label="Name"><input className={inputClass} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
          <Field label="City"><input className={inputClass} value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} /></Field>
          <Field label="Time zone" hint="IANA name, e.g. Asia/Kolkata"><input className={inputClass} value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} /></Field>
          {error !== null && <ErrorState error={error} />}
          <div className="flex gap-2">
            <Button variant="primary" onClick={() => void create()} disabled={!form.store_code || !form.name}>Create store</Button>
            <Button variant="ghost" onClick={() => setAdding(false)}>Cancel</Button>
          </div>
        </div>
      )}
    </Card>
  );
}

function StoreSettings({ store, onSaved }: { store: Store; onSaved: () => void }) {
  const [pos, setPos] = useState(store.pos_store_code ?? "");
  const [tz, setTz] = useState(store.timezone);
  const [error, setError] = useState<unknown>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const unassigned = useResource("pos-unassigned", (signal) => api<{ items: { pos_store_code: string; orders: number; first_date: string | null; last_date: string | null }[] }>("/api/pos/unassigned", { signal }));

  async function save() {
    setError(null);
    setMsg(null);
    try {
      await api(`/api/stores/${store.id}`, { method: "PATCH", json: { pos_store_code: pos || null, timezone: tz } });
      setMsg("Saved");
      onSaved();
      unassigned.reload();
    } catch (e) {
      setError(e);
    }
  }

  async function importCsv(file: File) {
    setError(null);
    setMsg(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const r = await api<{ inserted: number; duplicates_skipped: number; error_count: number }>("/api/pos/import", { method: "POST", body: form });
      setMsg(`Imported ${r.inserted} line items (${r.duplicates_skipped} already present, ${r.error_count} rejected).`);
      unassigned.reload();
    } catch (e) {
      setError(e);
    }
  }

  return (
    <Card>
      <CardTitle title="Store settings" hint={store.store_code} />
      <div className="space-y-2">
        <Field label="Time zone" hint="Used for days and hours on every chart."><input className={inputClass} value={tz} onChange={(e) => setTz(e.target.value)} /></Field>
        <Field label="POS store code" hint="The store_id value used in your POS export.">
          <input className={inputClass} value={pos} onChange={(e) => setPos(e.target.value)} list="pos-codes" />
          <datalist id="pos-codes">{unassigned.data?.items.map((u) => <option key={u.pos_store_code} value={u.pos_store_code} />)}</datalist>
        </Field>
        {unassigned.data && unassigned.data.items.length > 0 && (
          <Note>Unmapped POS codes: {unassigned.data.items.map((u) => `${u.pos_store_code} (${u.orders} orders, ${u.first_date}–${u.last_date})`).join(", ")}</Note>
        )}
        <div className="flex flex-wrap gap-2">
          <Button variant="primary" onClick={() => void save()}>Save</Button>
          <label className="inline-flex min-h-10 cursor-pointer items-center rounded-lg border border-[var(--border-color)] px-3 text-sm hover:border-[var(--border-hover)]">
            Import POS CSV
            <input type="file" accept=".csv,text/csv" className="sr-only" onChange={(e) => e.target.files?.[0] && void importCsv(e.target.files[0])} />
          </label>
        </div>
        {msg && <p className="text-sm text-emerald-300">{msg}</p>}
        {error !== null && <ErrorState error={error} />}
      </div>
    </Card>
  );
}

function AddCamera({ storeId, onAdded }: { storeId: string; onAdded: (c: Camera) => void }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<{ camera_code: string; name: string; camera_type: CameraType }>({ camera_code: "", name: "", camera_type: "zone" });
  const [error, setError] = useState<unknown>(null);
  if (!open) return <Button variant="ghost" className="mt-2" onClick={() => setOpen(true)}>Add camera</Button>;
  async function create() {
    setError(null);
    try {
      const c = await api<Camera>(`/api/stores/${storeId}/cameras`, { json: form });
      setOpen(false);
      setForm({ camera_code: "", name: "", camera_type: "zone" });
      onAdded(c);
    } catch (e) {
      setError(e);
    }
  }
  return (
    <div className="mt-3 space-y-2">
      <Field label="Code"><input className={inputClass} value={form.camera_code} onChange={(e) => setForm({ ...form, camera_code: e.target.value })} placeholder="CAM1" /></Field>
      <Field label="Name"><input className={inputClass} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
      <Field label="Type" hint="Entrance: counts entries with a line. Billing: queue and counter zones. Zone: shelves and displays.">
        <select className={inputClass} value={form.camera_type} onChange={(e) => setForm({ ...form, camera_type: e.target.value as CameraType })}>
          <option value="entrance">Entrance</option>
          <option value="zone">Zone</option>
          <option value="billing">Billing</option>
          <option value="other">Other</option>
        </select>
      </Field>
      {error !== null && <ErrorState error={error} />}
      <div className="flex gap-2">
        <Button variant="primary" onClick={() => void create()} disabled={!form.camera_code || !form.name}>Add</Button>
        <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
      </div>
    </div>
  );
}
