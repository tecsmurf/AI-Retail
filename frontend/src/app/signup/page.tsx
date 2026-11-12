"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/components/session";
import { Button, ErrorState, Field, Loading, Note, inputClass } from "@/components/ui";
import { api } from "@/lib/api";

/** A new customer creates their company and becomes its admin. */
export default function SignupPage() {
  const { signup } = useSession();
  const router = useRouter();
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [form, setForm] = useState({ company_name: "", full_name: "", email: "", password: "" });
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<{ signup_enabled: boolean }>("/api/auth/options").then((o) => setEnabled(o.signup_enabled), () => setEnabled(false));
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signup(form);
      router.replace("/onboarding");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="grid min-h-dvh place-items-center px-4 py-8">
      <form onSubmit={submit} className="card w-full max-w-sm space-y-4 p-6">
        <div>
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-purple-600 font-bold text-white">F</div>
          <h1 className="mt-4 text-xl font-semibold">Create your company account</h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            You become the admin. Add your stores and cameras next, then invite your store managers.
          </p>
        </div>
        {enabled === null ? <Loading /> : !enabled ? (
          <Note>Sign-up is turned off on this server. Ask your administrator for an account.</Note>
        ) : (
          <>
            <Field label="Company or store name">
              <input className={inputClass} required minLength={2} autoComplete="organization" value={form.company_name}
                onChange={set("company_name")} placeholder="Sharma Kirana Stores" />
            </Field>
            <Field label="Your name">
              <input className={inputClass} autoComplete="name" value={form.full_name} onChange={set("full_name")} />
            </Field>
            <Field label="Work email">
              <input className={inputClass} type="email" required autoComplete="username" value={form.email} onChange={set("email")} />
            </Field>
            <Field label="Password" hint="At least 10 characters">
              <input className={inputClass} type="password" required minLength={10} autoComplete="new-password"
                value={form.password} onChange={set("password")} />
            </Field>
            {error !== null && <ErrorState error={error} />}
            <Button type="submit" variant="primary" className="w-full" disabled={busy}>
              {busy ? "Creating account…" : "Create account"}
            </Button>
            <p className="text-xs text-[var(--text-muted)]">
              Your company&apos;s data is visible only to people you add. Footrail counts people anonymously and does not recognise faces.
            </p>
          </>
        )}
        <p className="text-center text-sm text-[var(--text-secondary)]">
          Already have an account? <Link href="/login" className="text-purple-300 underline">Sign in</Link>
        </p>
      </form>
    </div>
  );
}
