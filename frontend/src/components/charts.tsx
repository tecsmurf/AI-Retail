"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const AXIS = { fill: "#8b8ba3", fontSize: 11 };

function ChartTooltip({ active, payload, label, unit }: {
  active?: boolean; payload?: { value: number; name: string }[]; label?: string; unit?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-elevated)] px-3 py-2 text-xs shadow-lg">
      <div className="text-[var(--text-secondary)]">{label}</div>
      {payload.map((p) => (
        <div key={p.name} className="font-medium tabular-nums">
          {p.value === null || p.value === undefined ? "—" : p.value.toLocaleString("en-IN")}{unit ?? ""}
        </div>
      ))}
    </div>
  );
}

/** Simple vertical bars; fixed height so it renders predictably on phones. */
export function Bars({
  data, x, y, color = "#a855f7", height = 200, unit,
}: {
  data: object[]; x: string; y: string; color?: string; height?: number; unit?: string;
}) {
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
          <CartesianGrid vertical={false} stroke="#26263a" />
          <XAxis dataKey={x} tick={AXIS} tickLine={false} axisLine={false} interval="preserveStartEnd" minTickGap={12} />
          <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} width={44} />
          <Tooltip content={<ChartTooltip unit={unit} />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
          <Bar dataKey={y} fill={color} radius={[3, 3, 0, 0]} maxBarSize={28} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Horizontal labelled bars (no chart library) for ranked lists. */
export function RankBars({ rows, format = (n) => n.toLocaleString("en-IN"), color = "#a855f7" }: {
  rows: { label: string; value: number; sub?: string }[];
  format?: (n: number) => string;
  color?: string;
}) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <ul className="space-y-3">
      {rows.map((r) => (
        <li key={r.label}>
          <div className="mb-1 flex justify-between gap-3 text-sm">
            <span className="truncate">{r.label}</span>
            <span className="shrink-0 tabular-nums text-[var(--text-secondary)]">{format(r.value)}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-white/5">
            <div className="h-full rounded-full" style={{ width: `${(r.value / max) * 100}%`, background: color }} />
          </div>
          {r.sub && <div className="mt-1 text-xs text-[var(--text-muted)]">{r.sub}</div>}
        </li>
      ))}
    </ul>
  );
}
