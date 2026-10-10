"use client";

import { AlertTriangle, Info, Loader2 } from "lucide-react";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return <section className={cn("card p-4 sm:p-5", className)}>{children}</section>;
}

export function CardTitle({ title, hint, action }: { title: string; hint?: string; action?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-start justify-between gap-3">
      <div>
        <h2 className="text-sm font-semibold tracking-tight">{title}</h2>
        {hint && <p className="mt-0.5 text-xs text-[var(--text-muted)]">{hint}</p>}
      </div>
      {action}
    </div>
  );
}

export function Stat({
  label, value, sub, tone = "default", title,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "default" | "muted" | "warn";
  title?: string;
}) {
  return (
    <div className="card p-4" title={title}>
      <div className="text-xs text-[var(--text-secondary)]">{label}</div>
      <div className={cn("mt-1 text-2xl font-semibold tabular-nums tracking-tight",
        tone === "muted" && "text-[var(--text-muted)]", tone === "warn" && "text-amber-300")}>
        {value}
      </div>
      {sub && <div className="mt-1 text-xs leading-snug text-[var(--text-muted)]">{sub}</div>}
    </div>
  );
}

export function Badge({ tone = "neutral", children }: { tone?: "neutral" | "good" | "warn" | "bad" | "info"; children: React.ReactNode }) {
  const tones = {
    neutral: "bg-white/5 text-[var(--text-secondary)] border-white/10",
    good: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20",
    warn: "bg-amber-500/10 text-amber-300 border-amber-500/20",
    bad: "bg-rose-500/10 text-rose-300 border-rose-500/20",
    info: "bg-cyan-500/10 text-cyan-300 border-cyan-500/20",
  };
  return <span className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium", tones[tone])}>{children}</span>;
}

export function Button({
  variant = "secondary", className, ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger" }) {
  const v = {
    primary: "bg-purple-600 text-white hover:bg-purple-500 disabled:bg-purple-900",
    secondary: "border border-[var(--border-color)] bg-[var(--bg-elevated)] hover:border-[var(--border-hover)]",
    ghost: "hover:bg-white/5",
    danger: "border border-rose-500/30 text-rose-300 hover:bg-rose-500/10",
  };
  return (
    <button
      {...props}
      className={cn("inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-3 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60", v[variant], className)}
    />
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-8 text-sm text-[var(--text-muted)]" role="status">
      <Loader2 className="h-4 w-4 animate-spin" /> {label}…
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const msg = error instanceof ApiError || error instanceof Error ? error.message : "Something went wrong";
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-rose-500/20 bg-rose-500/5 p-4 text-sm text-rose-200" role="alert">
      <AlertTriangle className="h-4 w-4 shrink-0" />
      <span className="flex-1">{msg}</span>
      {onRetry && <Button variant="ghost" onClick={onRetry}>Retry</Button>}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-[var(--border-color)] p-6 text-center">
      <p className="text-sm font-medium">{title}</p>
      {children && <div className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-[var(--text-muted)]">{children}</div>}
    </div>
  );
}

export function Note({ children }: { children: React.ReactNode }) {
  return (
    <p className="flex gap-2 text-xs leading-relaxed text-[var(--text-muted)]">
      <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <span>{children}</span>
    </p>
  );
}

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: React.ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-[var(--text-secondary)]">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-[var(--text-muted)]">{hint}</span>}
    </label>
  );
}

export const inputClass =
  "w-full min-h-10 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 text-sm outline-none focus:border-purple-500";
