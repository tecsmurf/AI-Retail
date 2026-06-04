"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArrowLeft, TrendingUp, BarChart3, Calendar, Clock,
  Users, ShoppingCart, DollarSign, ArrowUpRight, ArrowDownRight,
  Download, Filter,
} from "lucide-react";
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  Legend, ComposedChart,
} from "recharts";
import { cn, formatNumber, formatCurrency, formatPercent } from "@/lib/utils";

// ── Historical Data (7 days) ──────────────────────────────────
const DAILY_DATA = [
  { day: "Mon", date: "Mar 3", visitors: 198, conversions: 42, revenue: 38200, avgDwell: 420, queueWait: 45 },
  { day: "Tue", date: "Mar 4", visitors: 215, conversions: 51, revenue: 44600, avgDwell: 395, queueWait: 38 },
  { day: "Wed", date: "Mar 5", visitors: 187, conversions: 38, revenue: 32100, avgDwell: 440, queueWait: 52 },
  { day: "Thu", date: "Mar 6", visitors: 234, conversions: 55, revenue: 47800, avgDwell: 410, queueWait: 42 },
  { day: "Fri", date: "Mar 7", visitors: 267, conversions: 64, revenue: 56200, avgDwell: 380, queueWait: 35 },
  { day: "Sat", date: "Mar 8", visitors: 312, conversions: 78, revenue: 68500, avgDwell: 355, queueWait: 28 },
  { day: "Sun", date: "Mar 9", visitors: 289, conversions: 71, revenue: 61400, avgDwell: 365, queueWait: 31 },
];

const WEEKLY_DATA = [
  { week: "W1 Feb", visitors: 1120, conversions: 245, revenue: 210500, peakDay: "Saturday" },
  { week: "W2 Feb", visitors: 1340, conversions: 298, revenue: 256800, peakDay: "Saturday" },
  { week: "W3 Feb", visitors: 1180, conversions: 261, revenue: 228400, peakDay: "Friday" },
  { week: "W4 Feb", visitors: 1450, conversions: 319, revenue: 278900, peakDay: "Saturday" },
  { week: "W1 Mar", visitors: 1702, conversions: 399, revenue: 348800, peakDay: "Saturday" },
];

const HOURLY_HEATMAP = [
  { hour: "9AM", mon: 12, tue: 15, wed: 11, thu: 14, fri: 18, sat: 28, sun: 22 },
  { hour: "10AM", mon: 22, tue: 25, wed: 19, thu: 24, fri: 30, sat: 42, sun: 35 },
  { hour: "11AM", mon: 35, tue: 38, wed: 32, thu: 40, fri: 44, sat: 55, sun: 48 },
  { hour: "12PM", mon: 42, tue: 45, wed: 38, thu: 48, fri: 52, sat: 62, sun: 55 },
  { hour: "1PM", mon: 38, tue: 40, wed: 35, thu: 42, fri: 48, sat: 58, sun: 50 },
  { hour: "2PM", mon: 30, tue: 32, wed: 28, thu: 35, fri: 40, sat: 52, sun: 45 },
  { hour: "3PM", mon: 25, tue: 28, wed: 22, thu: 30, fri: 35, sat: 48, sun: 40 },
  { hour: "4PM", mon: 28, tue: 30, wed: 25, thu: 32, fri: 38, sat: 50, sun: 42 },
  { hour: "5PM", mon: 32, tue: 35, wed: 30, thu: 38, fri: 42, sat: 55, sun: 48 },
  { hour: "6PM", mon: 35, tue: 38, wed: 32, thu: 40, fri: 45, sat: 58, sun: 50 },
  { hour: "7PM", mon: 28, tue: 30, wed: 25, thu: 32, fri: 38, sat: 48, sun: 42 },
  { hour: "8PM", mon: 18, tue: 20, wed: 15, thu: 22, fri: 28, sat: 38, sun: 30 },
];

const ZONE_TRENDS = [
  { zone: "Faces Canada", w1: 145, w2: 162, w3: 158, w4: 178, w5: 195, trend: "up", growth: 12.4 },
  { zone: "L'Oreal Paris", w1: 132, w2: 148, w3: 140, w4: 165, w5: 180, trend: "up", growth: 15.2 },
  { zone: "Makeup Station", w1: 98, w2: 105, w3: 112, w4: 120, w5: 135, trend: "up", growth: 8.5 },
  { zone: "Minimalist", w1: 110, w2: 95, w3: 102, w4: 88, w5: 82, trend: "down", growth: -7.8 },
  { zone: "Good Vibes", w1: 85, w2: 92, w3: 88, w4: 95, w5: 98, trend: "up", growth: 3.2 },
  { zone: "Billing Area", w1: 78, w2: 85, w3: 82, w4: 90, w5: 99, trend: "up", growth: 10.1 },
];

// ── Custom Tooltip ──────────────────────────────────────────────
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

// ── Heat Cell ─────────────────────────────────────────────────
function HeatCell({ value, max }: { value: number; max: number }) {
  const intensity = value / max;
  const bg = intensity > 0.8 ? "bg-purple-500" :
    intensity > 0.6 ? "bg-purple-500/80" :
    intensity > 0.4 ? "bg-purple-500/50" :
    intensity > 0.2 ? "bg-purple-500/30" : "bg-purple-500/10";
  return (
    <td className="p-1">
      <div className={cn("w-full h-8 rounded flex items-center justify-center text-[10px] font-medium", bg,
        intensity > 0.5 ? "text-white" : "text-purple-300"
      )}>
        {value}
      </div>
    </td>
  );
}

// ── Main Page ───────────────────────────────────────────────────
export default function AnalyticsPage() {
  const [timeRange, setTimeRange] = useState<"daily" | "weekly">("daily");

  // Summary stats
  const totalVisitors = DAILY_DATA.reduce((a, b) => a + b.visitors, 0);
  const totalRevenue = DAILY_DATA.reduce((a, b) => a + b.revenue, 0);
  const totalConversions = DAILY_DATA.reduce((a, b) => a + b.conversions, 0);
  const avgConvRate = totalConversions / totalVisitors;
  const avgDwell = DAILY_DATA.reduce((a, b) => a + b.avgDwell, 0) / DAILY_DATA.length;

  // WoW comparison
  const thisWeek = WEEKLY_DATA[WEEKLY_DATA.length - 1];
  const lastWeek = WEEKLY_DATA[WEEKLY_DATA.length - 2];
  const visitorGrowth = ((thisWeek.visitors - lastWeek.visitors) / lastWeek.visitors) * 100;
  const revenueGrowth = ((thisWeek.revenue - lastWeek.revenue) / lastWeek.revenue) * 100;

  const maxHeat = Math.max(...HOURLY_HEATMAP.flatMap(h => [h.mon, h.tue, h.wed, h.thu, h.fri, h.sat, h.sun]));

  return (
    <div className="min-h-screen gradient-mesh">
      {/* Header */}
      <header className="sticky top-0 z-50 glass-card rounded-none border-x-0 border-t-0">
        <div className="max-w-[1600px] mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="p-2 rounded-lg hover:bg-[var(--bg-card-hover)] transition-colors">
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-purple-400" />
              <h1 className="text-lg font-bold">Historical Analytics</h1>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex rounded-lg border border-[var(--border-color)] overflow-hidden">
              <button onClick={() => setTimeRange("daily")}
                className={cn("px-3 py-1.5 text-xs font-medium transition-colors",
                  timeRange === "daily" ? "bg-purple-500/20 text-purple-400" : "text-[var(--text-secondary)] hover:bg-[var(--bg-card-hover)]"
                )}>Daily</button>
              <button onClick={() => setTimeRange("weekly")}
                className={cn("px-3 py-1.5 text-xs font-medium transition-colors",
                  timeRange === "weekly" ? "bg-purple-500/20 text-purple-400" : "text-[var(--text-secondary)] hover:bg-[var(--bg-card-hover)]"
                )}>Weekly</button>
            </div>
            <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--border-color)] text-xs text-[var(--text-secondary)] hover:border-purple-500/40 transition-colors">
              <Download className="w-3.5 h-3.5" />
              Export CSV
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto px-4 sm:px-6 py-6 space-y-6">

        {/* ── Summary Cards ────────────────────────────────────── */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="glass-card p-4">
            <div className="flex items-center gap-2 mb-2">
              <Users className="w-4 h-4 text-purple-400" />
              <span className="text-xs text-[var(--text-muted)]">Total Visitors (7d)</span>
            </div>
            <div className="text-2xl font-bold">{formatNumber(totalVisitors)}</div>
            <div className={cn("text-xs flex items-center gap-0.5 mt-1", visitorGrowth > 0 ? "text-emerald-400" : "text-rose-400")}>
              {visitorGrowth > 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
              {Math.abs(visitorGrowth).toFixed(1)}% vs last week
            </div>
          </div>
          <div className="glass-card p-4">
            <div className="flex items-center gap-2 mb-2">
              <ShoppingCart className="w-4 h-4 text-emerald-400" />
              <span className="text-xs text-[var(--text-muted)]">Conversions (7d)</span>
            </div>
            <div className="text-2xl font-bold text-emerald-400">{totalConversions}</div>
            <div className="text-xs text-[var(--text-secondary)] mt-1">
              {formatPercent(avgConvRate)} avg rate
            </div>
          </div>
          <div className="glass-card p-4">
            <div className="flex items-center gap-2 mb-2">
              <DollarSign className="w-4 h-4 text-cyan-400" />
              <span className="text-xs text-[var(--text-muted)]">Revenue (7d)</span>
            </div>
            <div className="text-2xl font-bold">{formatCurrency(totalRevenue)}</div>
            <div className={cn("text-xs flex items-center gap-0.5 mt-1", revenueGrowth > 0 ? "text-emerald-400" : "text-rose-400")}>
              {revenueGrowth > 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
              {Math.abs(revenueGrowth).toFixed(1)}% vs last week
            </div>
          </div>
          <div className="glass-card p-4">
            <div className="flex items-center gap-2 mb-2">
              <Clock className="w-4 h-4 text-amber-400" />
              <span className="text-xs text-[var(--text-muted)]">Avg Dwell Time</span>
            </div>
            <div className="text-2xl font-bold">{Math.round(avgDwell / 60)}m {Math.round(avgDwell % 60)}s</div>
            <div className="text-xs text-[var(--text-secondary)] mt-1">Per visit avg</div>
          </div>
          <div className="glass-card p-4">
            <div className="flex items-center gap-2 mb-2">
              <Calendar className="w-4 h-4 text-rose-400" />
              <span className="text-xs text-[var(--text-muted)]">Peak Day</span>
            </div>
            <div className="text-2xl font-bold">Sat</div>
            <div className="text-xs text-[var(--text-secondary)] mt-1">312 visitors, ₹68.5K rev</div>
          </div>
        </div>

        {/* ── Visitor & Revenue Trend ──────────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 glass-card p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-purple-400" />
                <h2 className="text-lg font-semibold">
                  {timeRange === "daily" ? "Daily" : "Weekly"} Visitor & Revenue Trend
                </h2>
              </div>
            </div>
            <div className="h-[320px]">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={(timeRange === "daily" ? DAILY_DATA : WEEKLY_DATA) as any}>
                  <defs>
                    <linearGradient id="visitorGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#a855f7" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#a855f7" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                  <XAxis dataKey={timeRange === "daily" ? "day" : "week"} stroke="var(--text-muted)" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis yAxisId="left" stroke="var(--text-muted)" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis yAxisId="right" orientation="right" stroke="var(--text-muted)" fontSize={11} tickLine={false} axisLine={false}
                    tickFormatter={(v: number) => `₹${(v / 1000).toFixed(0)}K`} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend />
                  <Area yAxisId="left" type="monotone" dataKey="visitors" stroke="#a855f7" strokeWidth={2}
                    fill="url(#visitorGrad)" name="Visitors" />
                  <Bar yAxisId="right" dataKey="revenue" fill="#06b6d4" fillOpacity={0.6} radius={[4, 4, 0, 0]} name="Revenue (₹)" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Conversion Rate Trend */}
          <div className="glass-card p-5">
            <div className="flex items-center gap-2 mb-4">
              <ShoppingCart className="w-5 h-5 text-emerald-400" />
              <h2 className="text-lg font-semibold">Conversion Rate Trend</h2>
            </div>
            <div className="h-[320px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={DAILY_DATA.map(d => ({
                  ...d,
                  convRate: ((d.conversions / d.visitors) * 100).toFixed(1),
                }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                  <XAxis dataKey="day" stroke="var(--text-muted)" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="var(--text-muted)" fontSize={11} tickLine={false} axisLine={false}
                    domain={[15, 30]} tickFormatter={(v: number) => `${v}%`} />
                  <Tooltip content={<CustomTooltip />} />
                  <Line type="monotone" dataKey="convRate" stroke="#10b981" strokeWidth={2.5}
                    dot={{ r: 4, fill: "#10b981" }} name="Conversion %" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* ── Traffic Heatmap ─────────────────────────────────── */}
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Calendar className="w-5 h-5 text-purple-400" />
            <h2 className="text-lg font-semibold">Weekly Traffic Heatmap</h2>
            <span className="text-xs text-[var(--text-muted)] ml-2">(visitors per hour)</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-[var(--text-muted)]">
                  <th className="text-left py-2 px-2 w-16">Hour</th>
                  <th className="py-2 w-14">Mon</th>
                  <th className="py-2 w-14">Tue</th>
                  <th className="py-2 w-14">Wed</th>
                  <th className="py-2 w-14">Thu</th>
                  <th className="py-2 w-14">Fri</th>
                  <th className="py-2 w-14">Sat</th>
                  <th className="py-2 w-14">Sun</th>
                </tr>
              </thead>
              <tbody>
                {HOURLY_HEATMAP.map(row => (
                  <tr key={row.hour}>
                    <td className="text-[var(--text-secondary)] py-1 px-2 font-medium">{row.hour}</td>
                    <HeatCell value={row.mon} max={maxHeat} />
                    <HeatCell value={row.tue} max={maxHeat} />
                    <HeatCell value={row.wed} max={maxHeat} />
                    <HeatCell value={row.thu} max={maxHeat} />
                    <HeatCell value={row.fri} max={maxHeat} />
                    <HeatCell value={row.sat} max={maxHeat} />
                    <HeatCell value={row.sun} max={maxHeat} />
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center gap-2 mt-3 text-xs text-[var(--text-muted)]">
            <span>Low</span>
            <div className="flex gap-0.5">
              {[10, 30, 50, 80, 100].map(v => (
                <div key={v} className="w-6 h-3 rounded" style={{
                  background: `rgba(168, 85, 247, ${v / 100})`
                }} />
              ))}
            </div>
            <span>High</span>
          </div>
        </div>

        {/* ── Zone Popularity Trends ──────────────────────────── */}
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-5 h-5 text-purple-400" />
            <h2 className="text-lg font-semibold">Zone Popularity Trends</h2>
            <span className="text-xs text-[var(--text-muted)] ml-2">(5-week view)</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {ZONE_TRENDS.map(zone => (
              <div key={zone.zone} className="p-3 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-color)]/50">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-sm">{zone.zone}</span>
                  <span className={cn("flex items-center gap-0.5 text-xs font-medium",
                    zone.trend === "up" ? "text-emerald-400" : "text-rose-400"
                  )}>
                    {zone.trend === "up" ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                    {zone.growth > 0 ? "+" : ""}{zone.growth}%
                  </span>
                </div>
                <div className="h-[60px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={[
                      { w: "W1", v: zone.w1 },
                      { w: "W2", v: zone.w2 },
                      { w: "W3", v: zone.w3 },
                      { w: "W4", v: zone.w4 },
                      { w: "W5", v: zone.w5 },
                    ]}>
                      <defs>
                        <linearGradient id={`zg-${zone.zone}`} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={zone.trend === "up" ? "#10b981" : "#f43f5e"} stopOpacity={0.3} />
                          <stop offset="95%" stopColor={zone.trend === "up" ? "#10b981" : "#f43f5e"} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <Area type="monotone" dataKey="v"
                        stroke={zone.trend === "up" ? "#10b981" : "#f43f5e"}
                        strokeWidth={1.5}
                        fill={`url(#zg-${zone.zone})`} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
                <div className="flex justify-between text-[10px] text-[var(--text-muted)] mt-1">
                  <span>W1: {zone.w1}</span>
                  <span>Current: {zone.w5}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Queue Analytics Over Time ───────────────────────── */}
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="w-5 h-5 text-amber-400" />
            <h2 className="text-lg font-semibold">Queue Wait Time Trend</h2>
          </div>
          <div className="h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={DAILY_DATA}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                <XAxis dataKey="day" stroke="var(--text-muted)" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="var(--text-muted)" fontSize={11} tickLine={false} axisLine={false}
                  tickFormatter={(v: number) => `${v}s`} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="queueWait" fill="#f59e0b" fillOpacity={0.7} radius={[4, 4, 0, 0]} name="Avg Queue Wait (s)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <footer className="text-center py-4 text-xs text-[var(--text-muted)]">
          PurpleSol — AI Retail Intelligence Platform • Historical Analytics View
        </footer>
      </main>
    </div>
  );
}
