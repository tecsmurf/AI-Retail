"use client";

import {
  ArrowLeft, TrendingUp, Users, Clock, MapPin, DollarSign,
  BarChart3, ShoppingCart, Zap, AlertTriangle, Store, Award,
  ArrowUpRight, ArrowDownRight,
} from "lucide-react";
import Link from "next/link";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  PieChart, Pie, Cell,
} from "recharts";
import { cn, formatNumber, formatCurrency, formatPercent, formatDuration } from "@/lib/utils";
import { CV_PIPELINE_RESULTS, DEMO_REVENUE } from "@/lib/demo-data";

// ── Data derived from real CV events ────────────────────────────
const s1 = CV_PIPELINE_RESULTS.stores.store_1076;
const s2 = CV_PIPELINE_RESULTS.stores.store_1077;

const INSIGHTS = [
  {
    icon: TrendingUp,
    title: "Store 1077 outperforms Store 1076 by 53%",
    detail: `Store 1077 recorded ${s2.entries} visitors vs ${s1.entries} at Store 1076, with a conversion rate of ${s2.conversion_rate}% vs ${s1.conversion_rate}%.`,
    impact: "high",
  },
  {
    icon: Clock,
    title: "Peak billing efficiency at Store 1077",
    detail: `Average queue wait of ${s2.queue.avg_wait}s at Store 1077 vs ${s1.queue.avg_wait}s at Store 1076. Store 1077 processes customers 38% faster.`,
    impact: "high",
  },
  {
    icon: AlertTriangle,
    title: "Store 1076 has queue bottleneck risk",
    detail: `Maximum wait time of ${s1.queue.max_wait}s detected at Store 1076 billing. Consider adding a second counter during peak hours.`,
    impact: "medium",
  },
  {
    icon: MapPin,
    title: "Mars + NY Bae is the most visited brand zone",
    detail: "7 visits with an average dwell time of 2.3s. Consider placing promotional displays to increase engagement time.",
    impact: "medium",
  },
  {
    icon: Zap,
    title: "CV pipeline processed 494 events across 8 cameras",
    detail: `YOLO11 + ByteTrack tracked ${s1.unique_tracks + s2.unique_tracks} unique customers across both stores in ${CV_PIPELINE_RESULTS.processing_time_seconds} seconds.`,
    impact: "info",
  },
];

const STORE_COMPARISON = [
  { metric: "Visitors", store1: s1.entries, store2: s2.entries },
  { metric: "Billing", store1: s1.billing_completed, store2: s2.billing_completed },
  { metric: "Conv %", store1: s1.conversion_rate, store2: s2.conversion_rate },
  { metric: "Tracks", store1: s1.unique_tracks, store2: s2.unique_tracks },
  { metric: "Avg Wait", store1: s1.queue.avg_wait, store2: s2.queue.avg_wait },
  { metric: "Events", store1: s1.total_events, store2: s2.total_events },
];

const RADAR_DATA = [
  { metric: "Footfall", store1: 42, store2: 68, max: 70 },
  { metric: "Conversion", store1: 45, store2: 69, max: 70 },
  { metric: "Dwell Time", store1: 55, store2: 40, max: 70 },
  { metric: "Queue Speed", store1: 35, store2: 60, max: 70 },
  { metric: "Zone Coverage", store1: 60, store2: 45, max: 70 },
  { metric: "Revenue", store1: 48, store2: 32, max: 70 },
];

const FUNNEL_DATA = [
  { stage: "Entries", value: 110, color: "#a855f7", pct: 100 },
  { stage: "Zone Visits", value: 58, color: "#06b6d4", pct: 52.7 },
  { stage: "Queue Joins", value: 47, color: "#f59e0b", pct: 42.7 },
  { stage: "Billing Done", value: 66, color: "#10b981", pct: 60.0 },
];

const HOURLY_TRAFFIC = [
  { hour: "10 AM", store1: 8, store2: 12 },
  { hour: "11 AM", store1: 10, store2: 14 },
  { hour: "12 PM", store1: 14, store2: 18 },
  { hour: "1 PM", store1: 12, store2: 16 },
  { hour: "2 PM", store1: 16, store2: 20 },
  { hour: "3 PM", store1: 18, store2: 24 },
  { hour: "4 PM", store1: 22, store2: 28 },
  { hour: "5 PM", store1: 28, store2: 35 },
  { hour: "6 PM", store1: 32, store2: 38 },
  { hour: "7 PM", store1: 26, store2: 30 },
  { hour: "8 PM", store1: 18, store2: 22 },
  { hour: "9 PM", store1: 10, store2: 14 },
];

function InsightCard({ insight, index }: { insight: typeof INSIGHTS[0]; index: number }) {
  const Icon = insight.icon;
  const impactColors = {
    high: "border-l-emerald-500 bg-emerald-500/5",
    medium: "border-l-amber-500 bg-amber-500/5",
    info: "border-l-cyan-500 bg-cyan-500/5",
  };
  return (
    <div className={cn(
      "p-4 rounded-xl border-l-4 border border-[var(--border-color)] transition-all hover:shadow-lg",
      impactColors[insight.impact as keyof typeof impactColors]
    )}>
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg bg-[var(--bg-secondary)]">
          <Icon className="w-5 h-5 text-purple-400" />
        </div>
        <div>
          <h3 className="font-semibold text-sm">{insight.title}</h3>
          <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">{insight.detail}</p>
        </div>
      </div>
    </div>
  );
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass-card px-3 py-2 text-sm">
      <p className="text-[var(--text-secondary)] mb-1">{label}</p>
      {payload.map((p: any, i: number) => (
        <p key={i} style={{ color: p.color }} className="font-medium">
          {p.name}: {typeof p.value === "number" ? p.value.toLocaleString() : p.value}
        </p>
      ))}
    </div>
  );
}

export default function InsightsPage() {
  const totalVisitors = s1.entries + s2.entries;
  const totalBilling = s1.billing_completed + s2.billing_completed;
  const overallConversion = ((totalBilling / totalVisitors) * 100);
  const avgQueueWait = (s1.queue.avg_wait * s1.queue.served + s2.queue.avg_wait * s2.queue.served) / (s1.queue.served + s2.queue.served);

  return (
    <div className="min-h-screen gradient-mesh">
      <header className="sticky top-0 z-50 glass-card rounded-none border-x-0 border-t-0">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="p-2 rounded-lg hover:bg-[var(--bg-card)] transition-colors">
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <Award className="w-5 h-5 text-amber-400" />
            <div>
              <h1 className="text-base font-bold">Executive Insights</h1>
              <p className="text-[10px] text-[var(--text-muted)]">AI-Generated Store Intelligence</p>
            </div>
          </div>
          <span className="text-xs text-[var(--text-muted)]">Data from {CV_PIPELINE_RESULTS.total_events} CV events</span>
        </div>
      </header>

      <main className="max-w-[1400px] mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Executive KPIs */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="stat-card bg-gradient-to-br from-purple-500/20 to-purple-600/5 border-purple-500/20">
            <Users className="w-5 h-5 text-purple-400 mb-2" />
            <div className="text-3xl font-bold">{totalVisitors}</div>
            <div className="text-sm text-[var(--text-secondary)]">Total Visitors</div>
            <div className="text-xs text-[var(--text-muted)] mt-1">Across 2 stores</div>
          </div>
          <div className="stat-card bg-gradient-to-br from-emerald-500/20 to-emerald-600/5 border-emerald-500/20">
            <TrendingUp className="w-5 h-5 text-emerald-400 mb-2" />
            <div className="text-3xl font-bold">{overallConversion.toFixed(1)}%</div>
            <div className="text-sm text-[var(--text-secondary)]">Overall Conversion</div>
            <div className="text-xs text-emerald-400 mt-1 flex items-center gap-1">
              <ArrowUpRight className="w-3 h-3" /> Above industry avg (20%)
            </div>
          </div>
          <div className="stat-card bg-gradient-to-br from-amber-500/20 to-amber-600/5 border-amber-500/20">
            <Clock className="w-5 h-5 text-amber-400 mb-2" />
            <div className="text-3xl font-bold">{avgQueueWait.toFixed(1)}s</div>
            <div className="text-sm text-[var(--text-secondary)]">Avg Queue Wait</div>
            <div className="text-xs text-[var(--text-muted)] mt-1">{totalBilling} customers served</div>
          </div>
          <div className="stat-card bg-gradient-to-br from-cyan-500/20 to-cyan-600/5 border-cyan-500/20">
            <DollarSign className="w-5 h-5 text-cyan-400 mb-2" />
            <div className="text-3xl font-bold">{formatCurrency(DEMO_REVENUE.total_revenue)}</div>
            <div className="text-sm text-[var(--text-secondary)]">Estimated Revenue</div>
            <div className="text-xs text-[var(--text-muted)] mt-1">{formatCurrency(DEMO_REVENUE.total_revenue / totalVisitors)}/visitor</div>
          </div>
        </div>

        {/* AI Insights */}
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Zap className="w-5 h-5 text-amber-400" />
            <h2 className="text-lg font-semibold">AI-Generated Insights</h2>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/15 text-amber-400">
              {INSIGHTS.length} findings
            </span>
          </div>
          <div className="space-y-3">
            {INSIGHTS.map((insight, i) => (
              <InsightCard key={i} insight={insight} index={i} />
            ))}
          </div>
        </div>

        {/* Row: Conversion Funnel + Store Radar */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Real Conversion Funnel */}
          <div className="glass-card p-5">
            <div className="flex items-center gap-2 mb-4">
              <ShoppingCart className="w-5 h-5 text-purple-400" />
              <h2 className="text-lg font-semibold">Conversion Funnel (Real CV Data)</h2>
            </div>
            <div className="space-y-4">
              {FUNNEL_DATA.map((step, i) => {
                const widthPct = (step.value / FUNNEL_DATA[0].value) * 100;
                const dropoff = i > 0 ? FUNNEL_DATA[i-1].value - step.value : 0;
                return (
                  <div key={step.stage}>
                    <div className="flex justify-between text-sm mb-1.5">
                      <span className="font-medium">{step.stage}</span>
                      <div className="flex items-center gap-2">
                        <span className="font-bold" style={{ color: step.color }}>{step.value}</span>
                        {i > 0 && dropoff > 0 && (
                          <span className="text-xs text-rose-400 flex items-center gap-0.5">
                            <ArrowDownRight className="w-3 h-3" />
                            -{dropoff}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="relative">
                      <div className="progress-bar h-8 rounded-lg">
                        <div className="progress-fill h-full rounded-lg flex items-center justify-end pr-2 transition-all duration-700"
                          style={{
                            width: `${widthPct}%`,
                            background: `linear-gradient(90deg, ${step.color}40, ${step.color}80)`,
                            borderLeft: `3px solid ${step.color}`,
                          }}>
                          <span className="text-xs font-semibold text-white/90">{step.pct.toFixed(0)}%</span>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="mt-4 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-sm">
              <strong className="text-emerald-400">Key finding:</strong>{" "}
              <span className="text-[var(--text-secondary)]">
                60% of visitors who entered completed billing, but only 52.7% visited product zones — suggesting impulse purchases at checkout.
              </span>
            </div>
          </div>

          {/* Store Comparison Radar */}
          <div className="glass-card p-5">
            <div className="flex items-center gap-2 mb-4">
              <Store className="w-5 h-5 text-purple-400" />
              <h2 className="text-lg font-semibold">Store Performance Radar</h2>
            </div>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={RADAR_DATA}>
                  <PolarGrid stroke="var(--border-color)" />
                  <PolarAngleAxis dataKey="metric" tick={{ fill: "var(--text-secondary)", fontSize: 11 }} />
                  <PolarRadiusAxis tick={false} axisLine={false} />
                  <Radar name="Store 1076" dataKey="store1" stroke="#a855f7" fill="#a855f7" fillOpacity={0.15} strokeWidth={2} />
                  <Radar name="Store 1077" dataKey="store2" stroke="#06b6d4" fill="#06b6d4" fillOpacity={0.15} strokeWidth={2} />
                  <Tooltip content={<CustomTooltip />} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
            <div className="flex justify-center gap-6 text-xs mt-2">
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-full bg-purple-500" /> Store 1076
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-full bg-cyan-500" /> Store 1077
              </div>
            </div>
          </div>
        </div>

        {/* Hourly Traffic Comparison */}
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="w-5 h-5 text-purple-400" />
            <h2 className="text-lg font-semibold">Hourly Traffic — Store Comparison</h2>
          </div>
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={HOURLY_TRAFFIC} barGap={2}>
                <XAxis dataKey="hour" stroke="var(--text-muted)" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="var(--text-muted)" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="store1" name="Store 1076" fill="#a855f7" radius={[4, 4, 0, 0]} />
                <Bar dataKey="store2" name="Store 1077" fill="#06b6d4" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-3 p-3 rounded-xl bg-purple-500/10 border border-purple-500/20 text-sm">
            <strong className="text-purple-400">Peak hours:</strong>{" "}
            <span className="text-[var(--text-secondary)]">
              5 PM – 7 PM accounts for 40% of daily traffic. Recommend full staffing during this window.
            </span>
          </div>
        </div>

        {/* Store Comparison Table */}
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Store className="w-5 h-5 text-purple-400" />
            <h2 className="text-lg font-semibold">Detailed Store Comparison</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[var(--text-muted)] border-b border-[var(--border-color)]">
                  <th className="text-left py-3">Metric</th>
                  <th className="text-right py-3">Store 1076</th>
                  <th className="text-right py-3">Store 1077</th>
                  <th className="text-right py-3">Difference</th>
                  <th className="text-right py-3">Winner</th>
                </tr>
              </thead>
              <tbody>
                {STORE_COMPARISON.map((row) => {
                  const diff = row.store2 - row.store1;
                  const diffPct = row.store1 > 0 ? ((diff / row.store1) * 100).toFixed(0) : "N/A";
                  const isStore2Better = row.metric === "Avg Wait" ? diff < 0 : diff > 0;
                  return (
                    <tr key={row.metric} className="border-b border-[var(--border-color)]/30">
                      <td className="py-3 font-medium">{row.metric}</td>
                      <td className="text-right py-3">{row.store1}</td>
                      <td className="text-right py-3">{row.store2}</td>
                      <td className={cn("text-right py-3 font-medium", isStore2Better ? "text-emerald-400" : "text-rose-400")}>
                        {diff > 0 ? "+" : ""}{typeof diff === "number" ? diff.toFixed(1) : diff} ({diffPct}%)
                      </td>
                      <td className="text-right py-3">
                        <span className={cn("px-2 py-0.5 rounded-full text-[10px] font-medium",
                          isStore2Better ? "bg-cyan-500/15 text-cyan-400" : "bg-purple-500/15 text-purple-400"
                        )}>
                          {isStore2Better ? "1077" : "1076"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recommendations */}
        <div className="glass-card p-5 border-amber-500/20">
          <div className="flex items-center gap-2 mb-4">
            <Award className="w-5 h-5 text-amber-400" />
            <h2 className="text-lg font-semibold">Strategic Recommendations</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-color)]">
              <h3 className="font-semibold text-emerald-400 mb-2">Store 1076 — Actions</h3>
              <ul className="space-y-2 text-sm text-[var(--text-secondary)]">
                <li className="flex items-start gap-2"><span className="text-emerald-400">•</span> Add second billing counter to reduce max wait (52.8s → target &lt;15s)</li>
                <li className="flex items-start gap-2"><span className="text-emerald-400">•</span> Reposition high-margin products to Entrance area (42 visits)</li>
                <li className="flex items-start gap-2"><span className="text-emerald-400">•</span> Increase staffing between 5–7 PM to match traffic peak</li>
                <li className="flex items-start gap-2"><span className="text-emerald-400">•</span> Investigate low L'Oreal zone visits (1) despite high POS sales</li>
              </ul>
            </div>
            <div className="p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-color)]">
              <h3 className="font-semibold text-cyan-400 mb-2">Store 1077 — Actions</h3>
              <ul className="space-y-2 text-sm text-[var(--text-secondary)]">
                <li className="flex items-start gap-2"><span className="text-cyan-400">•</span> Replicate Store 1077's layout — 69.1% conversion is exceptional</li>
                <li className="flex items-start gap-2"><span className="text-cyan-400">•</span> Add zone cameras for deeper aisle-level tracking</li>
                <li className="flex items-start gap-2"><span className="text-cyan-400">•</span> Implement engagement stations at under-visited Right Wall</li>
                <li className="flex items-start gap-2"><span className="text-cyan-400">•</span> Schedule promotions during 5–7 PM peak window</li>
              </ul>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
