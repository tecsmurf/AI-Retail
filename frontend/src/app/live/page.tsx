"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft, Activity, Users, Clock, MapPin, ShoppingCart,
  AlertTriangle, Zap, Eye, Radio, Wifi, WifiOff,
} from "lucide-react";
import { cn, formatDuration } from "@/lib/utils";

// ── Simulated Live Data ──────────────────────────────────────────
interface LiveEvent {
  id: string;
  type: "ENTRY" | "EXIT" | "ZONE_ENTER" | "ZONE_EXIT" | "QUEUE_ENTER" | "QUEUE_COMPLETED";
  customer_id: string;
  zone?: string;
  store: string;
  timestamp: Date;
  confidence?: number;
}

const ZONE_NAMES = ["Faces Canada", "L'Oreal Paris", "Minimalist", "Makeup Station", "Good Vibes", "NY Bae", "Billing Area"];
const STORE_NAMES = ["Store 1076 — Mumbai Central", "Store 1077 — Mumbai West"];

function generateEvent(): LiveEvent {
  const types: LiveEvent["type"][] = ["ENTRY", "EXIT", "ZONE_ENTER", "ZONE_EXIT", "QUEUE_ENTER", "QUEUE_COMPLETED"];
  const type = types[Math.floor(Math.random() * types.length)];
  const needsZone = ["ZONE_ENTER", "ZONE_EXIT", "QUEUE_ENTER", "QUEUE_COMPLETED"].includes(type);
  return {
    id: `evt-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    type,
    customer_id: `CUS-${Math.floor(Math.random() * 200).toString().padStart(3, "0")}`,
    zone: needsZone ? (type.startsWith("QUEUE") ? "Billing Area" : ZONE_NAMES[Math.floor(Math.random() * (ZONE_NAMES.length - 1))]) : undefined,
    store: STORE_NAMES[Math.floor(Math.random() * 2)],
    timestamp: new Date(),
    confidence: 0.75 + Math.random() * 0.2,
  };
}

const EVENT_ICONS: Record<string, { icon: typeof Users; color: string; bg: string }> = {
  ENTRY: { icon: Users, color: "text-emerald-400", bg: "bg-emerald-500/15" },
  EXIT: { icon: Users, color: "text-gray-400", bg: "bg-gray-500/15" },
  ZONE_ENTER: { icon: MapPin, color: "text-purple-400", bg: "bg-purple-500/15" },
  ZONE_EXIT: { icon: MapPin, color: "text-purple-300", bg: "bg-purple-500/10" },
  QUEUE_ENTER: { icon: Clock, color: "text-amber-400", bg: "bg-amber-500/15" },
  QUEUE_COMPLETED: { icon: ShoppingCart, color: "text-cyan-400", bg: "bg-cyan-500/15" },
};

// ── Live Stats ──────────────────────────────────────────────────
function LiveStats({ events }: { events: LiveEvent[] }) {
  const inStore = new Set<string>();
  const inQueue = new Set<string>();
  const entries = events.filter(e => e.type === "ENTRY").length;
  const exits = events.filter(e => e.type === "EXIT").length;
  const purchases = events.filter(e => e.type === "QUEUE_COMPLETED").length;

  events.forEach(e => {
    if (e.type === "ENTRY") inStore.add(e.customer_id);
    if (e.type === "EXIT") inStore.delete(e.customer_id);
    if (e.type === "QUEUE_ENTER") inQueue.add(e.customer_id);
    if (e.type === "QUEUE_COMPLETED" || e.type === "EXIT") inQueue.delete(e.customer_id);
  });

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
      <div className="glass-card p-3 text-center">
        <div className="text-xs text-[var(--text-muted)] mb-1">In-Store Now</div>
        <div className="text-2xl font-bold text-emerald-400">{inStore.size}</div>
        <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse-slow mx-auto mt-1" />
      </div>
      <div className="glass-card p-3 text-center">
        <div className="text-xs text-[var(--text-muted)] mb-1">In Queue</div>
        <div className="text-2xl font-bold text-amber-400">{inQueue.size}</div>
      </div>
      <div className="glass-card p-3 text-center">
        <div className="text-xs text-[var(--text-muted)] mb-1">Entries Today</div>
        <div className="text-2xl font-bold text-purple-400">{entries}</div>
      </div>
      <div className="glass-card p-3 text-center">
        <div className="text-xs text-[var(--text-muted)] mb-1">Exits Today</div>
        <div className="text-2xl font-bold text-gray-400">{exits}</div>
      </div>
      <div className="glass-card p-3 text-center">
        <div className="text-xs text-[var(--text-muted)] mb-1">Purchases</div>
        <div className="text-2xl font-bold text-cyan-400">{purchases}</div>
      </div>
    </div>
  );
}

// ── Event Feed Item ─────────────────────────────────────────────
function EventItem({ event, isNew }: { event: LiveEvent; isNew: boolean }) {
  const config = EVENT_ICONS[event.type];
  const Icon = config.icon;
  const time = event.timestamp.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

  return (
    <div className={cn(
      "flex items-center gap-3 p-3 rounded-xl border transition-all duration-500",
      isNew ? "border-purple-500/50 bg-purple-500/5 scale-[1.01]" : "border-[var(--border-color)]/30 bg-[var(--bg-secondary)]"
    )}>
      <div className={cn("p-2 rounded-lg shrink-0", config.bg)}>
        <Icon className={cn("w-4 h-4", config.color)} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={cn("text-xs font-semibold px-2 py-0.5 rounded", config.bg, config.color)}>
            {event.type.replace("_", " ")}
          </span>
          <span className="text-xs text-[var(--text-muted)]">{event.customer_id}</span>
        </div>
        <div className="flex items-center gap-2 mt-0.5 text-xs text-[var(--text-secondary)]">
          {event.zone && <span className="flex items-center gap-1"><MapPin className="w-3 h-3" />{event.zone}</span>}
          <span>{event.store.split("—")[0].trim()}</span>
          {event.confidence && <span className="text-[var(--text-muted)]">{(event.confidence * 100).toFixed(0)}% conf</span>}
        </div>
      </div>
      <span className="text-xs text-[var(--text-muted)] shrink-0 font-mono">{time}</span>
    </div>
  );
}

// ── Zone Activity Map ───────────────────────────────────────────
function ZoneActivity({ events }: { events: LiveEvent[] }) {
  const zoneCounts: Record<string, number> = {};
  events.filter(e => e.type === "ZONE_ENTER" && e.zone).forEach(e => {
    zoneCounts[e.zone!] = (zoneCounts[e.zone!] || 0) + 1;
  });

  const max = Math.max(...Object.values(zoneCounts), 1);

  return (
    <div className="space-y-2">
      {ZONE_NAMES.map(zone => {
        const count = zoneCounts[zone] || 0;
        const width = (count / max) * 100;
        return (
          <div key={zone} className="flex items-center gap-3">
            <span className="text-xs text-[var(--text-secondary)] w-28 truncate">{zone}</span>
            <div className="flex-1 progress-bar">
              <div className="progress-fill bg-gradient-to-r from-purple-500 to-cyan-500"
                style={{ width: `${Math.max(width, 3)}%`, transition: "width 0.5s ease" }} />
            </div>
            <span className="text-xs font-medium w-8 text-right">{count}</span>
          </div>
        );
      })}
    </div>
  );
}

// ── Main Live Page ──────────────────────────────────────────────
export default function LivePage() {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [newEventIds, setNewEventIds] = useState<Set<string>>(new Set());

  // Simulate live event stream
  useEffect(() => {
    // Initial batch
    const initial = Array.from({ length: 15 }, () => {
      const e = generateEvent();
      e.timestamp = new Date(Date.now() - Math.random() * 60000);
      return e;
    }).sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
    setEvents(initial);
    setIsConnected(true);

    if (isPaused) return;

    const interval = setInterval(() => {
      const newEvent = generateEvent();
      setNewEventIds(prev => new Set([...prev, newEvent.id]));
      setEvents(prev => [newEvent, ...prev].slice(0, 100));

      // Clear "new" highlight after animation
      setTimeout(() => {
        setNewEventIds(prev => {
          const next = new Set(prev);
          next.delete(newEvent.id);
          return next;
        });
      }, 1500);
    }, 2000 + Math.random() * 3000);

    return () => clearInterval(interval);
  }, [isPaused]);

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
              <Radio className="w-5 h-5 text-emerald-400 animate-pulse-slow" />
              <h1 className="text-lg font-bold">Live Store Monitor</h1>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium",
              isConnected ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-400" :
              "bg-rose-500/10 border border-rose-500/20 text-rose-400"
            )}>
              {isConnected ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
              {isConnected ? "Connected" : "Disconnected"}
            </div>
            <button onClick={() => setIsPaused(!isPaused)}
              className={cn("px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors",
                isPaused ? "border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10" :
                "border-amber-500/30 text-amber-400 hover:bg-amber-500/10"
              )}>
              {isPaused ? "▶ Resume" : "⏸ Pause"}
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto px-4 sm:px-6 py-6 space-y-6">

        {/* Live Stats */}
        <LiveStats events={events} />

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Event Feed */}
          <div className="lg:col-span-2 glass-card p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Activity className="w-5 h-5 text-purple-400" />
                <h2 className="text-lg font-semibold">Live Event Feed</h2>
              </div>
              <span className="text-xs text-[var(--text-muted)]">{events.length} events</span>
            </div>
            <div className="space-y-2 max-h-[600px] overflow-y-auto pr-2 custom-scrollbar">
              {events.slice(0, 30).map(event => (
                <EventItem key={event.id} event={event} isNew={newEventIds.has(event.id)} />
              ))}
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            {/* Zone Activity */}
            <div className="glass-card p-5">
              <div className="flex items-center gap-2 mb-4">
                <MapPin className="w-5 h-5 text-purple-400" />
                <h2 className="font-semibold">Zone Activity</h2>
              </div>
              <ZoneActivity events={events} />
            </div>

            {/* Recent Alerts */}
            <div className="glass-card p-5">
              <div className="flex items-center gap-2 mb-4">
                <AlertTriangle className="w-5 h-5 text-amber-400" />
                <h2 className="font-semibold">Live Alerts</h2>
              </div>
              <div className="space-y-2">
                <div className="p-3 rounded-xl bg-amber-500/5 border border-amber-500/20">
                  <div className="flex items-center gap-2 text-sm">
                    <Zap className="w-4 h-4 text-amber-400" />
                    <span className="font-medium text-amber-400">Queue Building</span>
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] mt-1">
                    3+ customers waiting at billing for &gt;45s
                  </p>
                  <span className="text-[10px] text-[var(--text-muted)]">2 minutes ago</span>
                </div>
                <div className="p-3 rounded-xl bg-purple-500/5 border border-purple-500/20">
                  <div className="flex items-center gap-2 text-sm">
                    <Eye className="w-4 h-4 text-purple-400" />
                    <span className="font-medium text-purple-400">High Traffic Zone</span>
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] mt-1">
                    Faces Canada zone at 2x normal capacity
                  </p>
                  <span className="text-[10px] text-[var(--text-muted)]">5 minutes ago</span>
                </div>
              </div>
            </div>

            {/* Store Status */}
            <div className="glass-card p-5">
              <div className="flex items-center gap-2 mb-4">
                <Eye className="w-5 h-5 text-cyan-400" />
                <h2 className="font-semibold">Camera Status</h2>
              </div>
              <div className="space-y-2">
                {["CAM1 — Zone View", "CAM2 — Zone View", "CAM3 — Entry", "CAM5 — Billing"].map(cam => (
                  <div key={cam} className="flex items-center justify-between p-2 rounded-lg bg-[var(--bg-secondary)]">
                    <span className="text-xs">{cam}</span>
                    <div className="flex items-center gap-1.5">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      <span className="text-[10px] text-emerald-400">Online</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <footer className="text-center py-4 text-xs text-[var(--text-muted)]">
          PurpleSol — AI Retail Intelligence Platform • Live Monitor
        </footer>
      </main>
    </div>
  );
}
