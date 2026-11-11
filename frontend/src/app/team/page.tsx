"use client";

import { useState } from "react";
import { useDashboard } from "@/components/dashboard";
import { useSession } from "@/components/session";
import { Badge, Button, Card, CardTitle, Empty, ErrorState, Field, Loading, Note, PageHeader, inputClass } from "@/components/ui";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { ROLE_HELP, ROLE_LABELS, type Region, type Role, type Store, type User } from "@/lib/types";
import { cn, relativeTime } from "@/lib/utils";

const ROLES = Object.keys(ROLE_LABELS) as Role[];
const scoped = (role: Role) => role === "regional_manager" || role === "store_manager";

export default function TeamPage() {
  const { user: me, isAdmin } = useSession();
  const d = useDashboard();
  const users = useResource(isAdmin ? "team" : null, (signal) => api<User[]>("/api/users", { signal }));
  const regions = useResource(isAdmin ? "team-regions" : null, (signal) =>
    api<{ items: Region[] }>("/api/org/regions", { signal }));
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);

  if (!isAdmin) {
    return (
      <>
        <PageHeader title="Team" />
        <Note>Only administrators can manage the team.</Note>
      </>
    );
  }
  const stores = d.stores ?? [];
  const regionList = regions.data?.items ?? [];

  return (
    <>
      <PageHeader title="Team" subtitle={`People who can sign in to ${me?.org_name ?? "your organisation"}`}
        action={!adding ? <Button variant="primary" onClick={() => setAdding(true)}>Add person</Button> : undefined} />
      <div className="space-y-4">
        {adding && (
          <PersonForm stores={stores} regions={regionList} onCancel={() => setAdding(false)}
            onSaved={() => { setAdding(false); users.reload(); }} />
        )}
        <Card>
          <CardTitle title="People" hint={users.data ? `${users.data.filter((u) => u.is_active).length} active` : undefined} />
          {users.error && <ErrorState error={users.error} onRetry={users.reload} />}
          {users.loading && !users.data && <Loading />}
          {users.data && users.data.length === 0 && <Empty title="No one yet" />}
          {users.data && (
            <ul className="divide-y divide-[var(--border-color)]">
              {users.data.map((u) => (
                <li key={u.id} className="py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">
                        {u.full_name || u.email}{u.id === me?.id && <span className="text-[var(--text-muted)]"> (you)</span>}
                      </div>
                      <div className="truncate text-xs text-[var(--text-muted)]">
                        {u.full_name ? `${u.email} · ` : ""}{u.last_login_at ? `last sign-in ${relativeTime(u.last_login_at)}` : "never signed in"}
                      </div>
                    </div>
                    <Badge tone={u.role === "admin" ? "info" : "neutral"}>{ROLE_LABELS[u.role] ?? u.role}</Badge>
                    {!u.is_active && <Badge tone="warn">Deactivated</Badge>}
                    <Button variant="ghost" onClick={() => setEditing(editing === u.id ? null : u.id)}>
                      {editing === u.id ? "Close" : "Edit"}
                    </Button>
                  </div>
                  {scoped(u.role) && editing !== u.id && (
                    <div className="mt-1 text-xs text-[var(--text-secondary)]">{accessSummary(u, stores, regionList)}</div>
                  )}
                  {editing === u.id && (
                    <div className="mt-3">
                      <PersonForm user={u} isSelf={u.id === me?.id} stores={stores} regions={regionList}
                        onCancel={() => setEditing(null)} onSaved={() => { setEditing(null); users.reload(); }} />
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <CardTitle title="What each role can do" />
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            {ROLES.map((r) => (
              <div key={r}><dt className="font-medium">{ROLE_LABELS[r]}</dt><dd className="text-xs text-[var(--text-muted)]">{ROLE_HELP[r]}</dd></div>
            ))}
          </dl>
        </Card>
      </div>
    </>
  );
}

function accessSummary(u: User, stores: Store[], regions: Region[]): string {
  const r = u.region_ids.map((id) => regions.find((x) => x.id === id)?.name).filter(Boolean);
  const s = u.store_ids.map((id) => stores.find((x) => x.id === id)?.name).filter(Boolean);
  if (!r.length && !s.length) return "No stores assigned yet: this person sees nothing.";
  return [r.length ? `Regions: ${r.join(", ")}` : "", s.length ? `Stores: ${s.join(", ")}` : ""].filter(Boolean).join(" · ");
}

function CheckList({ label, items, selected, onChange, empty }: {
  label: string; items: { id: string; name: string }[]; selected: string[]; onChange: (ids: string[]) => void; empty: string;
}) {
  return (
    <fieldset>
      <legend className="mb-1 text-xs font-medium text-[var(--text-secondary)]">{label}</legend>
      {items.length === 0 ? <p className="text-xs text-[var(--text-muted)]">{empty}</p> : (
        <div className="max-h-48 space-y-1 overflow-y-auto rounded-lg border border-[var(--border-color)] p-2">
          {items.map((it) => (
            <label key={it.id} className="flex min-h-8 items-center gap-2 text-sm">
              <input type="checkbox" className="h-4 w-4 accent-purple-500" checked={selected.includes(it.id)}
                onChange={(e) => onChange(e.target.checked ? [...selected, it.id] : selected.filter((x) => x !== it.id))} />
              <span className="truncate">{it.name}</span>
            </label>
          ))}
        </div>
      )}
    </fieldset>
  );
}

/** Add a person (no `user`) or edit one. */
function PersonForm({ user, isSelf = false, stores, regions, onSaved, onCancel }: {
  user?: User; isSelf?: boolean; stores: Store[]; regions: Region[]; onSaved: () => void; onCancel: () => void;
}) {
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>(user?.role ?? "store_manager");
  const [storeIds, setStoreIds] = useState<string[]>(user?.store_ids ?? []);
  const [regionIds, setRegionIds] = useState<string[]>(user?.region_ids ?? []);
  const [error, setError] = useState<unknown>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      await fn();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  const grants = scoped(role) ? { store_ids: storeIds, region_ids: regionIds } : { store_ids: [], region_ids: [] };
  const save = () => run(async () => {
    if (user) {
      await api(`/api/users/${user.id}`, { method: "PATCH", json: { full_name: fullName, ...(isSelf ? {} : { role }), ...grants } });
    } else {
      await api("/api/users", { json: { email, password, full_name: fullName || null, role, ...grants } });
    }
    onSaved();
  });
  const setActive = (active: boolean) => run(async () => {
    await api(`/api/users/${user!.id}`, { method: "PATCH", json: { is_active: active } });
    onSaved();
  });
  const resetPassword = () => run(async () => {
    await api(`/api/users/${user!.id}/password`, { json: { new_password: password } });
    setPassword("");
    setMsg("Password changed. They have been signed out everywhere; give them the new password yourself.");
  });

  const body = (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        {!user && (
          <Field label="Email">
            <input className={inputClass} type="email" autoComplete="off" value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
        )}
        <Field label="Name">
          <input className={inputClass} value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </Field>
        {!user && (
          <Field label="Starting password" hint="At least 10 characters. Share it with them yourself; no email is sent.">
            <input className={inputClass} type="text" autoComplete="off" value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
        )}
        <Field label="Role" hint={isSelf ? "You cannot change your own role." : ROLE_HELP[role]}>
          <select className={inputClass} value={role} disabled={isSelf} onChange={(e) => setRole(e.target.value as Role)}>
            {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
          </select>
        </Field>
      </div>
      {scoped(role) && (
        <div className="grid gap-3 sm:grid-cols-2">
          <CheckList label="Regions (every store in them)" items={regions} selected={regionIds} onChange={setRegionIds}
            empty="No regions yet. Add them under Cameras & zones." />
          <CheckList label="Individual stores" items={stores} selected={storeIds} onChange={setStoreIds} empty="No stores yet." />
        </div>
      )}
      {scoped(role) && storeIds.length === 0 && regionIds.length === 0 && (
        <Note>Pick at least one region or store, otherwise this person will see nothing.</Note>
      )}
      {error !== null && <ErrorState error={error} />}
      {msg && <p className="text-sm text-emerald-300">{msg}</p>}
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" disabled={busy || (!user && (!email || password.length < 10))} onClick={() => void save()}>
          {user ? "Save" : "Add person"}
        </Button>
        <Button variant="ghost" onClick={onCancel}>Cancel</Button>
        {user && !isSelf && (
          user.is_active
            ? <Button variant="danger" className="sm:ml-auto" disabled={busy} onClick={() => void setActive(false)}>Deactivate</Button>
            : <Button className="sm:ml-auto" disabled={busy} onClick={() => void setActive(true)}>Reactivate</Button>
        )}
      </div>
      {user && !isSelf && (
        <div className="border-t border-[var(--border-color)] pt-3">
          <Field label="Set a new password" hint="Signs them out on every device.">
            <div className="flex gap-2">
              <input className={cn(inputClass, "flex-1")} type="text" autoComplete="off" value={password}
                onChange={(e) => setPassword(e.target.value)} placeholder="At least 10 characters" />
              <Button disabled={busy || password.length < 10} onClick={() => void resetPassword()}>Set password</Button>
            </div>
          </Field>
        </div>
      )}
    </div>
  );
  return user ? body : <Card><CardTitle title="Add a person" />{body}</Card>;
}
