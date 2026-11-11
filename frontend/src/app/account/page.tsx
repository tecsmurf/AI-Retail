"use client";

import { useState } from "react";
import { useSession } from "@/components/session";
import { Button, Card, CardTitle, ErrorState, Field, Note, PageHeader, inputClass } from "@/components/ui";
import { api } from "@/lib/api";
import { ROLE_LABELS } from "@/lib/types";

/** Your own profile, password and (for admins) the company name. */
export default function AccountPage() {
  const { user, isAdmin, refresh, logout } = useSession();
  if (!user) return null;
  return (
    <>
      <PageHeader title="Account" subtitle={`${user.email} · ${ROLE_LABELS[user.role] ?? user.role} at ${user.org_name}`} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Profile initial={user.full_name ?? ""} onSaved={refresh} />
        {isAdmin && <Company initial={user.org_name} onSaved={refresh} />}
        <Password />
        <Card>
          <CardTitle title="Sessions" hint="Use this if you signed in on a shared or lost device." />
          <Button onClick={() => void logout(true)}>Sign out on all devices</Button>
        </Card>
      </div>
    </>
  );
}

function useSave() {
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    setDone(false);
    try {
      await fn();
      setDone(true);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return { error, done, busy, run };
}

function Profile({ initial, onSaved }: { initial: string; onSaved: () => Promise<void> }) {
  const [name, setName] = useState(initial);
  const s = useSave();
  return (
    <Card>
      <CardTitle title="Your name" />
      <Field label="Full name"><input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} /></Field>
      {s.error !== null && <div className="mt-3"><ErrorState error={s.error} /></div>}
      <div className="mt-3 flex items-center gap-3">
        <Button variant="primary" disabled={s.busy} onClick={() => void s.run(async () => {
          await api("/api/auth/me", { method: "PATCH", json: { full_name: name } });
          await onSaved();
        })}>Save</Button>
        {s.done && <span className="text-sm text-emerald-400">Saved</span>}
      </div>
    </Card>
  );
}

function Company({ initial, onSaved }: { initial: string; onSaved: () => Promise<void> }) {
  const [name, setName] = useState(initial);
  const s = useSave();
  return (
    <Card>
      <CardTitle title="Company" hint="Shown to everyone in your company and on reports." />
      <Field label="Company name"><input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} /></Field>
      {s.error !== null && <div className="mt-3"><ErrorState error={s.error} /></div>}
      <div className="mt-3 flex items-center gap-3">
        <Button variant="primary" disabled={s.busy || name.trim().length < 2} onClick={() => void s.run(async () => {
          await api("/api/org", { method: "PATCH", json: { name } });
          await onSaved();
        })}>Save</Button>
        {s.done && <span className="text-sm text-emerald-400">Saved</span>}
      </div>
    </Card>
  );
}

function Password() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const s = useSave();
  return (
    <Card>
      <CardTitle title="Password" hint="Changing it signs you out on your other devices." />
      <div className="space-y-3">
        <Field label="Current password">
          <input className={inputClass} type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
        </Field>
        <Field label="New password" hint="At least 10 characters">
          <input className={inputClass} type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
        </Field>
      </div>
      {s.error !== null && <div className="mt-3"><ErrorState error={s.error} /></div>}
      <div className="mt-3 flex items-center gap-3">
        <Button variant="primary" disabled={s.busy || !current || next.length < 10} onClick={() => void s.run(async () => {
          await api("/api/auth/password", { json: { current_password: current, new_password: next } });
          setCurrent("");
          setNext("");
        })}>Change password</Button>
        {s.done && <span className="text-sm text-emerald-400">Password changed</span>}
      </div>
      {!s.done && <div className="mt-3"><Note>Forgot it? Ask your company&apos;s admin to set a new one on the Team page.</Note></div>}
    </Card>
  );
}
