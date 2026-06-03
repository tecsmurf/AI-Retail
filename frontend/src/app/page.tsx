"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Store, BarChart3, Users, ShoppingCart, TrendingUp,
  AlertTriangle, Map, Route, Activity, Bell, ChevronDown,
  Zap, Eye, Clock, DollarSign, ArrowUpRight, ArrowDownRight, Cpu, Video,
  Flame, Award,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, AreaChart, Area, CartesianGrid,
} from "recharts";
import { cn, formatNumber, formatCurrency, formatPercent, formatDuration, getRelativeTime, SEVERITY_COLORS } from "@/lib/utils";
import {
  DEMO_STORES, DEMO_OVERVIEW, DEMO_HOURLY, DEMO_ZONES,
  DEMO_CONVERSION, DEMO_QUEUE, DEMO_TOP_PATHS,
  DEMO_JOURNEY_ANALYTICS, DEMO_ALERTS, DEMO_DEMOGRAPHICS,
  DEMO_REVENUE, CV_PIPELINE_RESULTS,
} from "@/lib/demo-data";

// ── Stat Card Component ────────────────────────────────────────
function StatCard({
  title, value, subtitle, icon: Icon, trend, trendValue, color = "purple",
}: {
  title: string; value: string; subtitle?: string;
  icon: any; trend?: "up" | "down"; trendValue?: string;
  color?: "purple" | "cyan" | "emerald" | "amber" | "rose";
}) {
  const colorMap = {
    purple: "from-purple-500/20 to-purple-600/5 text-purple-400 border-purple-500/20",
    cyan: "from-cyan-500/20 to-cyan-600/5 text-cyan-400 border-cyan-500/20",
    emerald: "from-emerald-500/20 to-emerald-600/5 text-emerald-400 border-emerald-500/20",
    amber: "from-amber-500/20 to-amber-600/5 text-amber-400 border-amber-500/20",
    rose: "from-rose-500/20 to-rose-600/5 text-rose-400 border-rose-500/20",
  };
  const iconBg = {
    purple: "bg-purple-500/15 text-purple-400",
    cyan: "bg-cyan-500/15 text-cyan-400",
    emerald: "bg-emerald-500/15 text-emerald-400",
    amber: "bg-amber-500/15 text-amber-400",
    rose: "bg-rose-500/15 text-rose-400",
  };
  return (
    <div className={cn("stat-card bg-gradient-to-br", colorMap[color])}>
      <div className="flex items-start justify-between mb-3">
        <div className={cn("p-2.5 rounded-xl", iconBg[color])}>
          <Icon className="w-5 h-5" />
        </div>
        {trend && (
          <div className={cn("flex items-center gap-1 text-xs font-medium",
            trend === "up" ? "text-emerald-400" : "text-rose-400"
          )}>
            {trend === "up" ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
            {trendValue}
          </div>
        )}
      </div>
      <div className="text-2xl font-bold tracking-tight">{value}</div>
      <div className="text-sm text-[var(--text-secondary)] mt-1">{title}</div>
      {subtitle && <div className="text-xs text-[var(--text-muted)] mt-0.5">{subtitle}</div>}
    </div>
  );
}

// ── Section Header ──────────────────────────────────────────────
function SectionHeader({ title, icon: Icon, action }: {
  title: string; icon: any; action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-2.5">
        <Icon className="w-5 h-5 text-purple-400" />
        <h2 className="text-lg font-semibold">{title}</h2>
      </div>
      {action}
    </div>
  );
}

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

// ── Conversion Funnel ───────────────────────────────────────────
function ConversionFunnel() {
  const steps = [
    { label: "Visitors", value: DEMO_CONVERSION.total_visitors, color: "#a855f7" },
    { label: "Zone Visits", value: DEMO_CONVERSION.zone_visitors, color: "#06b6d4" },
    { label: "Interactions", value: DEMO_CONVERSION.product_interactions, color: "#f59e0b" },
    { label: "Billing", value: DEMO_CONVERSION.billing_visitors, color: "#10b981" },
    { label: "Purchases", value: DEMO_CONVERSION.purchases, color: "#22c55e" },
  ];
  const max = steps[0].value;
  return (
    <div className="space-y-3">
      {steps.map((step, i) => {
        const width = (step.value / max) * 100;
        const rate = i > 0 ? ((step.value / steps[i - 1].value) * 100).toFixed(0) : "100";
        return (
          <div key={step.label}>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-[var(--text-secondary)]">{step.label}</span>
              <span className="font-medium">{step.value} <span className="text-[var(--text-muted)]">({rate}%)</span></span>
            </div>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${width}%`, background: step.color }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Zone Ranking Table ──────────────────────────────────────────
function ZoneTable() {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[var(--text-muted)] border-b border-[var(--border-color)]">
            <th className="text-left py-3 px-2">#</th>
            <th className="text-left py-3">Zone</th>
            <th className="text-right py-3">Visits</th>
            <th className="text-right py-3">Visitors</th>
            <th className="text-right py-3">Avg Dwell</th>
          </tr>
        </thead>
        <tbody>
          {DEMO_ZONES.slice(0, 8).map((z) => (
            <tr key={z.zone_name} className="border-b border-[var(--border-color)]/50 hover:bg-[var(--bg-card-hover)] transition-colors">
              <td className="py-2.5 px-2 text-[var(--text-muted)]">{z.popularity_rank}</td>
              <td className="py-2.5">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full" style={{
                    background: z.zone_type === "SHELF" ? "#a855f7" :
                      z.zone_type === "DISPLAY" ? "#06b6d4" : "#10b981"
                  }} />
                  {z.zone_name}
                </div>
              </td>
              <td className="text-right py-2.5 font-medium">{z.total_visits}</td>
              <td className="text-right py-2.5">{z.unique_visitors}</td>
              <td className="text-right py-2.5 text-[var(--text-secondary)]">{formatDuration(z.avg_dwell_seconds)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Journey Path Visualization ──────────────────────────────────
function JourneyPaths() {
  return (
    <div className="space-y-3">
      {DEMO_TOP_PATHS.map((path, i) => (
        <div key={i} className="p-3 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-color)]/50 hover:border-purple-500/30 transition-all">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            {path.path.map((step, j) => (
              <span key={j} className="flex items-center gap-1.5">
                <span className={cn(
                  "px-2 py-0.5 rounded-md text-xs font-medium",
                  step === "ENTRY" ? "bg-emerald-500/15 text-emerald-400" :
                  step === "EXIT" ? "bg-gray-500/15 text-gray-400" :
                  step === "Billing" ? "bg-amber-500/15 text-amber-400" :
                  "bg-purple-500/15 text-purple-300"
                )}>
                  {step}
                </span>
                {j < path.path.length - 1 && <span className="text-[var(--text-muted)]">→</span>}
              </span>
            ))}
          </div>
          <div className="flex gap-4 text-xs text-[var(--text-secondary)]">
            <span>{path.count} customers</span>
            <span>Avg {formatDuration(path.avg_duration_seconds)}</span>
            <span className={path.conversion_rate > 0 ? "text-emerald-400" : "text-[var(--text-muted)]"}>
              {path.conversion_rate > 0 ? "✓ Conversion" : "Browse only"}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Alert List ──────────────────────────────────────────────────
function AlertList() {
  return (
    <div className="space-y-2">
      {DEMO_ALERTS.map((alert) => (
        <div key={alert.id} className={cn(
          "p-3 rounded-xl border transition-all",
          alert.is_read ? "bg-[var(--bg-secondary)] border-[var(--border-color)]/30" :
          "bg-[var(--bg-secondary)] border-l-2",
          !alert.is_read && alert.severity === "high" && "border-l-rose-500",
          !alert.is_read && alert.severity === "medium" && "border-l-amber-500",
        )}>
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0"
                style={{ color: SEVERITY_COLORS[alert.severity] }} />
              <div>
                <p className="text-sm font-medium">{alert.title}</p>
                <p className="text-xs text-[var(--text-secondary)] mt-0.5">{alert.message}</p>
              </div>
            </div>
            <span className="text-xs text-[var(--text-muted)] whitespace-nowrap ml-2">
              {getRelativeTime(alert.created_at)}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Main Dashboard ──────────────────────────────────────────────
export default function Dashboard() {
  const [activeStore, setActiveStore] = useState(0);
  const store = DEMO_STORES[activeStore];

  const pieData = Object.entries(DEMO_DEMOGRAPHICS.gender).map(([k, v]) => ({
    name: k === "F" ? "Female" : "Male", value: v,
  }));
  const PIE_COLORS = ["#a855f7", "#06b6d4"];

  const ageData = Object.entries(DEMO_DEMOGRAPHICS.age_buckets).map(([k, v]) => ({
    name: k, value: v,
  }));

  return (
    <div className="min-h-screen gradient-mesh">
      {/* ── Header ─────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 glass-card rounded-none border-x-0 border-t-0">
        <div className="max-w-[1600px] mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl gradient-purple flex items-center justify-center glow-purple">
              <Eye className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight">PurpleSol</h1>
              <p className="text-[10px] text-[var(--text-muted)] -mt-0.5 tracking-wider uppercase">Retail Intelligence</p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Store Selector */}
            <div className="relative">
              <button className="flex items-center gap-2 px-3 py-2 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] text-sm hover:border-purple-500/40 transition-colors"
                onClick={() => setActiveStore(activeStore === 0 ? 1 : 0)}>
                <Store className="w-4 h-4 text-purple-400" />
                <span className="max-w-[200px] truncate">{store.name}</span>
                <ChevronDown className="w-3.5 h-3.5 text-[var(--text-muted)]" />
              </button>
            </div>

            {/* Live Indicator */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse-slow" />
              <span className="text-xs text-emerald-400 font-medium">LIVE</span>
            </div>

            {/* Alerts */}
            <button className="relative p-2 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] hover:border-purple-500/40 transition-colors">
              <Bell className="w-4.5 h-4.5 text-[var(--text-secondary)]" />
              <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-rose-500 text-[10px] text-white flex items-center justify-center font-bold">
                3
              </div>
            </button>
          </div>
        </div>
      </header>

      {/* ── Main Content ───────────────────────────────────── */}
      <main className="max-w-[1600px] mx-auto px-4 sm:px-6 py-6 space-y-6">

        {/* ── Quick Navigation ──────────────────────────────── */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Link href="/heatmap" className="glass-card p-4 flex items-center gap-3 hover:border-rose-500/40 transition-all group">
            <div className="p-2.5 rounded-xl bg-rose-500/15 text-rose-400 group-hover:scale-110 transition-transform">
              <Flame className="w-5 h-5" />
            </div>
            <div>
              <div className="font-semibold text-sm">Store Layout Heatmap</div>
              <div className="text-xs text-[var(--text-secondary)]">Customer movement overlay</div>
            </div>
          </Link>
          <Link href="/journeys" className="glass-card p-4 flex items-center gap-3 hover:border-purple-500/40 transition-all group">
            <div className="p-2.5 rounded-xl bg-purple-500/15 text-purple-400 group-hover:scale-110 transition-transform">
              <Route className="w-5 h-5" />
            </div>
            <div>
              <div className="font-semibold text-sm">Journey Replay</div>
              <div className="text-xs text-[var(--text-secondary)]">Animated customer paths</div>
            </div>
          </Link>
          <Link href="/insights" className="glass-card p-4 flex items-center gap-3 hover:border-amber-500/40 transition-all group">
            <div className="p-2.5 rounded-xl bg-amber-500/15 text-amber-400 group-hover:scale-110 transition-transform">
              <Award className="w-5 h-5" />
            </div>
            <div>
              <div className="font-semibold text-sm">Executive Insights</div>
              <div className="text-xs text-[var(--text-secondary)]">AI-generated intelligence</div>
            </div>
          </Link>
        </div>

        {/* ── KPI Cards ────────────────────────────────────── */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <StatCard icon={Users} title="Visitors Today" value={formatNumber(DEMO_OVERVIEW.visitors_today)} trend="up" trendValue="+12.4%" color="purple" />
          <StatCard icon={Activity} title="Active Now" value={String(DEMO_OVERVIEW.active_visitors)} subtitle="In-store" color="cyan" />
          <StatCard icon={TrendingUp} title="Conversion Rate" value={formatPercent(DEMO_OVERVIEW.conversion_rate)} trend="up" trendValue="+3.2%" color="emerald" />
          <StatCard icon={Clock} title="Avg Dwell Time" value={formatDuration(DEMO_OVERVIEW.avg_dwell_time)} color="amber" />
          <StatCard icon={DollarSign} title="Revenue" value={formatCurrency(DEMO_OVERVIEW.revenue_today)} trend="up" trendValue="+8.1%" color="emerald" />
          <StatCard icon={AlertTriangle} title="Active Alerts" value={String(DEMO_OVERVIEW.active_alerts)} color="rose" />
        </div>

        {/* ── Row 2: Hourly + Conversion ───────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 glass-card p-5">
            <SectionHeader title="Hourly Footfall" icon={BarChart3} />
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={DEMO_HOURLY}>
                  <defs>
                    <linearGradient id="purpleGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#a855f7" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#a855f7" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                  <XAxis dataKey="label" stroke="var(--text-muted)" fontSize={11} tickLine={false} axisLine={false}
                    interval={2} />
                  <YAxis stroke="var(--text-muted)" fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area type="monotone" dataKey="visitors" stroke="#a855f7" strokeWidth={2}
                    fill="url(#purpleGrad)" name="Visitors" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="glass-card p-5">
            <SectionHeader title="Conversion Funnel" icon={ShoppingCart} />
            <ConversionFunnel />
            <div className="mt-4 pt-4 border-t border-[var(--border-color)]/50 grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs text-[var(--text-muted)]">Revenue/Visitor</div>
                <div className="text-lg font-bold text-emerald-400">{formatCurrency(DEMO_CONVERSION.revenue_per_visitor)}</div>
              </div>
              <div>
                <div className="text-xs text-[var(--text-muted)]">Avg Basket</div>
                <div className="text-lg font-bold text-cyan-400">{formatCurrency(DEMO_CONVERSION.avg_basket_value)}</div>
              </div>
            </div>
          </div>
        </div>

        {/* ── Row 3: Zone Analytics + Queue ─────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 glass-card p-5">
            <SectionHeader title="Zone Performance" icon={Map} />
            <ZoneTable />
          </div>

          <div className="glass-card p-5 space-y-5">
            <div>
              <SectionHeader title="Queue Status" icon={Users} />
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-xl bg-[var(--bg-secondary)]">
                  <div className="text-xs text-[var(--text-muted)]">Avg Wait</div>
                  <div className="text-xl font-bold text-amber-400">{formatDuration(DEMO_QUEUE.avg_wait_seconds)}</div>
                </div>
                <div className="p-3 rounded-xl bg-[var(--bg-secondary)]">
                  <div className="text-xs text-[var(--text-muted)]">Queue Now</div>
                  <div className="text-xl font-bold text-cyan-400">{DEMO_QUEUE.current_queue_length}</div>
                </div>
                <div className="p-3 rounded-xl bg-[var(--bg-secondary)]">
                  <div className="text-xs text-[var(--text-muted)]">Served</div>
                  <div className="text-xl font-bold text-emerald-400">{DEMO_QUEUE.total_served}</div>
                </div>
                <div className="p-3 rounded-xl bg-[var(--bg-secondary)]">
                  <div className="text-xs text-[var(--text-muted)]">Abandoned</div>
                  <div className="text-xl font-bold text-rose-400">{formatPercent(DEMO_QUEUE.abandonment_rate)}</div>
                </div>
              </div>
            </div>

            <div>
              <SectionHeader title="Demographics" icon={Users} />
              <div className="flex items-center justify-center h-[140px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={pieData} cx="50%" cy="50%" innerRadius={40} outerRadius={60}
                      paddingAngle={4} dataKey="value" strokeWidth={0}>
                      {pieData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i]} />)}
                    </Pie>
                    <Tooltip content={<CustomTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex justify-center gap-4 text-xs">
                {pieData.map((d, i) => (
                  <div key={d.name} className="flex items-center gap-1.5">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ background: PIE_COLORS[i] }} />
                    <span className="text-[var(--text-secondary)]">{d.name}: {d.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* ── Row 4: Journey Paths + Alerts ─────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="glass-card p-5">
            <SectionHeader title="Top Customer Journeys" icon={Route} />
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="p-2.5 rounded-xl bg-[var(--bg-secondary)] text-center">
                <div className="text-xs text-[var(--text-muted)]">Total</div>
                <div className="text-lg font-bold">{DEMO_JOURNEY_ANALYTICS.total_journeys}</div>
              </div>
              <div className="p-2.5 rounded-xl bg-[var(--bg-secondary)] text-center">
                <div className="text-xs text-[var(--text-muted)]">Avg Duration</div>
                <div className="text-lg font-bold">{formatDuration(DEMO_JOURNEY_ANALYTICS.avg_journey_duration)}</div>
              </div>
              <div className="p-2.5 rounded-xl bg-[var(--bg-secondary)] text-center">
                <div className="text-xs text-[var(--text-muted)]">Avg Zones</div>
                <div className="text-lg font-bold">{DEMO_JOURNEY_ANALYTICS.avg_zones_visited.toFixed(1)}</div>
              </div>
            </div>
            <JourneyPaths />
          </div>

          <div className="glass-card p-5">
            <SectionHeader title="Anomaly Center" icon={AlertTriangle}
              action={<span className="badge badge-danger">3 Active</span>} />
            <AlertList />

            {/* Revenue Top Brands */}
            <div className="mt-5 pt-4 border-t border-[var(--border-color)]/50">
              <SectionHeader title="Top Brands by Revenue" icon={DollarSign} />
              <div className="space-y-2">
                {DEMO_REVENUE.top_brands.slice(0, 5).map((b) => {
                  const pct = (b.revenue / DEMO_REVENUE.total_revenue) * 100;
                  return (
                    <div key={b.brand}>
                      <div className="flex justify-between text-sm mb-1">
                        <span>{b.brand}</span>
                        <span className="font-medium text-emerald-400">{formatCurrency(b.revenue)}</span>
                      </div>
                      <div className="progress-bar">
                        <div className="progress-fill bg-gradient-to-r from-purple-500 to-cyan-500" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* ── Row 5: Multi-Store Comparison ──────────────────── */}
        <div className="glass-card p-5">
          <SectionHeader title="Multi-Store Comparison" icon={Store} />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {DEMO_STORES.map((s, i) => (
              <div key={s.id} className={cn(
                "p-4 rounded-xl border transition-all cursor-pointer",
                i === activeStore ? "border-purple-500/50 bg-purple-500/5" : "border-[var(--border-color)] bg-[var(--bg-secondary)]"
              )} onClick={() => setActiveStore(i)}>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-semibold">{s.name}</h3>
                  <span className="badge badge-success">Active</span>
                </div>
                <div className="grid grid-cols-4 gap-2 text-center text-sm">
                  <div>
                    <div className="text-[var(--text-muted)] text-xs">Visitors</div>
                    <div className="font-bold">{i === 0 ? 247 : 189}</div>
                  </div>
                  <div>
                    <div className="text-[var(--text-muted)] text-xs">Conv %</div>
                    <div className="font-bold text-emerald-400">{i === 0 ? "23.4" : "19.8"}%</div>
                  </div>
                  <div>
                    <div className="text-[var(--text-muted)] text-xs">Revenue</div>
                    <div className="font-bold">{i === 0 ? "₹48.7K" : "₹32.1K"}</div>
                  </div>
                  <div>
                    <div className="text-[var(--text-muted)] text-xs">Cameras</div>
                    <div className="font-bold">{s.camera_count}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Row 6: CV Pipeline Results ──────────────────── */}
        <div className="glass-card p-5 border-cyan-500/20 glow-cyan">
          <SectionHeader title="CV Pipeline — Real CCTV Processing Results" icon={Cpu}
            action={<span className="badge badge-info">8 Videos Processed</span>} />
          <p className="text-sm text-[var(--text-secondary)] mb-4">
            Real-time person detection and tracking results from actual store CCTV footage using <strong className="text-cyan-400">YOLO11</strong> + <strong className="text-purple-400">ByteTrack</strong>
          </p>

          {/* Pipeline Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 mb-5">
            <div className="p-3 rounded-xl bg-[var(--bg-secondary)] text-center">
              <div className="text-xs text-[var(--text-muted)]">Total Events</div>
              <div className="text-xl font-bold text-cyan-400">{CV_PIPELINE_RESULTS.total_events}</div>
            </div>
            <div className="p-3 rounded-xl bg-[var(--bg-secondary)] text-center">
              <div className="text-xs text-[var(--text-muted)]">Videos</div>
              <div className="text-xl font-bold">{CV_PIPELINE_RESULTS.total_videos}</div>
            </div>
            <div className="p-3 rounded-xl bg-[var(--bg-secondary)] text-center">
              <div className="text-xs text-[var(--text-muted)]">Entries Detected</div>
              <div className="text-xl font-bold text-emerald-400">{CV_PIPELINE_RESULTS.event_breakdown.ENTRY}</div>
            </div>
            <div className="p-3 rounded-xl bg-[var(--bg-secondary)] text-center">
              <div className="text-xs text-[var(--text-muted)]">Zone Events</div>
              <div className="text-xl font-bold text-purple-400">{CV_PIPELINE_RESULTS.event_breakdown.ZONE_ENTER}</div>
            </div>
            <div className="p-3 rounded-xl bg-[var(--bg-secondary)] text-center">
              <div className="text-xs text-[var(--text-muted)]">Billing</div>
              <div className="text-xl font-bold text-amber-400">{CV_PIPELINE_RESULTS.event_breakdown.QUEUE_COMPLETED}</div>
            </div>
            <div className="p-3 rounded-xl bg-[var(--bg-secondary)] text-center">
              <div className="text-xs text-[var(--text-muted)]">Processing</div>
              <div className="text-xl font-bold">{CV_PIPELINE_RESULTS.processing_time_seconds}s</div>
            </div>
          </div>

          {/* Per-Store CV Results */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(CV_PIPELINE_RESULTS.stores).map(([code, data]) => (
              <div key={code} className="p-4 rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Video className="w-4 h-4 text-cyan-400" />
                    <h4 className="font-semibold">{data.name}</h4>
                  </div>
                  <span className="text-xs text-[var(--text-muted)]">{code}</span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center text-sm mb-3">
                  <div>
                    <div className="text-[var(--text-muted)] text-xs">Entries</div>
                    <div className="font-bold text-emerald-400">{data.entries}</div>
                  </div>
                  <div>
                    <div className="text-[var(--text-muted)] text-xs">Conv Rate</div>
                    <div className="font-bold text-purple-400">{data.conversion_rate}%</div>
                  </div>
                  <div>
                    <div className="text-[var(--text-muted)] text-xs">Tracks</div>
                    <div className="font-bold">{data.unique_tracks}</div>
                  </div>
                </div>
                {/* Queue metrics */}
                <div className="flex gap-3 text-xs">
                  <span className="text-[var(--text-secondary)]">Queue: <strong className="text-amber-400">{data.queue.served} served</strong></span>
                  <span className="text-[var(--text-secondary)]">Avg wait: <strong>{data.queue.avg_wait.toFixed(1)}s</strong></span>
                  <span className="text-[var(--text-secondary)]">Max: <strong className="text-rose-400">{data.queue.max_wait.toFixed(1)}s</strong></span>
                </div>
                {/* Zone detections */}
                {data.zones_detected.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-[var(--border-color)]/50">
                    <div className="text-xs text-[var(--text-muted)] mb-1">Zones detected:</div>
                    <div className="flex flex-wrap gap-1.5">
                      {data.zones_detected.map((z: any) => (
                        <span key={z.name} className="px-2 py-0.5 rounded-md text-xs bg-purple-500/10 text-purple-300">
                          {z.name} ({z.visits})
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Event Type Breakdown */}
          <div className="mt-4 pt-4 border-t border-[var(--border-color)]/50">
            <div className="text-sm font-medium mb-2">Event Type Breakdown</div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(CV_PIPELINE_RESULTS.event_breakdown).map(([type, count]) => {
                const colors: Record<string, string> = {
                  ENTRY: "bg-emerald-500/15 text-emerald-400",
                  EXIT: "bg-gray-500/15 text-gray-400",
                  ZONE_ENTER: "bg-purple-500/15 text-purple-400",
                  ZONE_EXIT: "bg-purple-500/10 text-purple-300",
                  QUEUE_ENTER: "bg-amber-500/15 text-amber-400",
                  QUEUE_COMPLETED: "bg-cyan-500/15 text-cyan-400",
                };
                return (
                  <span key={type} className={cn("px-3 py-1.5 rounded-lg text-xs font-medium", colors[type] || "bg-gray-500/15 text-gray-400")}>
                    {type}: {count}
                  </span>
                );
              })}
            </div>
          </div>
        </div>

        {/* ── Footer ─────────────────────────────────────────── */}
        <footer className="text-center py-6 text-xs text-[var(--text-muted)]">
          <p>PurpleSol — AI Retail Intelligence Platform • Built for Purplle Hackathon 2026</p>
          <p className="mt-1">Powered by YOLO11 + ByteTrack + FastAPI + Next.js</p>
        </footer>
      </main>
    </div>
  );
}
