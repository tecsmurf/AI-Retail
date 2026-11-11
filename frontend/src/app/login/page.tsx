"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useSession } from "@/components/session";
import { Button, ErrorState, Field, inputClass } from "@/components/ui";
import { api } from "@/lib/api";
import { OVERVIEW_PATH } from "@/lib/routes";

function LoginForm() {
  const { login } = useSession();
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [signupOn, setSignupOn] = useState(false);

  useEffect(() => {
    api<{ signup_enabled: boolean }>("/api/auth/options").then((o) => setSignupOn(o.signup_enabled), () => setSignupOn(false));
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      const next = params.get("next");
      router.replace(next && next.startsWith("/") && !next.startsWith("//") ? next : OVERVIEW_PATH);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="card w-full max-w-sm space-y-4 p-6">
      <div>
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-purple-600 font-bold text-white">P</div>
        <h1 className="mt-4 text-xl font-semibold">Sign in to PurpleSol</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          {signupOn ? "Store teams get their account from their company's admin." : "Accounts are created by an administrator."}
        </p>
      </div>
      <Field label="Email">
        <input className={inputClass} type="email" autoComplete="username" required value={email}
          onChange={(e) => setEmail(e.target.value)} />
      </Field>
      <Field label="Password">
        <input className={inputClass} type="password" autoComplete="current-password" required value={password}
          onChange={(e) => setPassword(e.target.value)} />
      </Field>
      {error !== null && <ErrorState error={error} />}
      <Button type="submit" variant="primary" className="w-full" disabled={busy}>
        {busy ? "Signing in…" : "Sign in"}
      </Button>
      {signupOn && (
        <p className="text-center text-sm text-[var(--text-secondary)]">
          New to PurpleSol? <Link href="/signup" className="text-purple-300 underline">Create a company account</Link>
        </p>
      )}
    </form>
  );
}

export default function LoginPage() {
  return (
    <div className="grid min-h-dvh place-items-center px-4">
      <Suspense>
        <LoginForm />
      </Suspense>
    </div>
  );
}
