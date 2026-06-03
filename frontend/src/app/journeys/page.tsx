"use client";

import { useState, useEffect } from "react";
import {
  ArrowLeft, Route, Play, Pause, SkipForward, Clock, MapPin, ShoppingCart,
} from "lucide-react";
import Link from "next/link";
import { cn, formatDuration } from "@/lib/utils";

// ── Sample customer journeys from CV data ───────────────────────
const JOURNEYS = [
  {
    id: "store_1076_CAM3_T0012",
    label: "Customer #12",
    store: "Store 1076",
    type: "conversion",
    steps: [
      { zone: "Entrance", time: "10:15:02", dwell: 3, type: "ENTRANCE" },
      { zone: "Faces Canada", time: "10:15:35", dwell: 45, type: "SHELF" },
      { zone: "Mars + NY Bae", time: "10:16:20", dwell: 28, type: "SHELF" },
      { zone: "L'Oreal", time: "10:17:08", dwell: 62, type: "SHELF" },
      { zone: "Cash Counter", time: "10:18:30", dwell: 15, type: "BILLING" },
      { zone: "Exit", time: "10:19:05", dwell: 0, type: "EXIT" },
    ],
    totalDuration: 243,
  },
  {
    id: "store_1077_CAM1_T0008",
    label: "Customer #8",
    store: "Store 1077",
    type: "browse",
    steps: [
      { zone: "Entrance", time: "10:22:10", dwell: 2, type: "ENTRANCE" },
      { zone: "Left Wall", time: "10:22:45", dwell: 38, type: "SHELF" },
      { zone: "Center Display 1", time: "10:23:33", dwell: 55, type: "DISPLAY" },
      { zone: "Makeup Area", time: "10:24:48", dwell: 72, type: "DISPLAY" },
      { zone: "Exit", time: "10:26:15", dwell: 0, type: "EXIT" },
    ],
    totalDuration: 245,
  },
  {
    id: "store_1076_CAM3_T0025",
    label: "Customer #25",
    store: "Store 1076",
    type: "conversion",
    steps: [
      { zone: "Entrance", time: "14:05:12", dwell: 4, type: "ENTRANCE" },
      { zone: "Minimalist", time: "14:05:45", dwell: 85, type: "SHELF" },
      { zone: "Aqualogica", time: "14:07:22", dwell: 42, type: "SHELF" },
      { zone: "Foxtale", time: "14:08:18", dwell: 30, type: "SHELF" },
      { zone: "Cash Counter", time: "14:09:10", dwell: 22, type: "BILLING" },
      { zone: "Exit", time: "14:09:52", dwell: 0, type: "EXIT" },
    ],
    totalDuration: 280,
  },
  {
    id: "store_1076_CAM3_T0031",
    label: "Customer #31",
    store: "Store 1076",
    type: "bounce",
    steps: [
      { zone: "Entrance", time: "16:30:05", dwell: 5, type: "ENTRANCE" },
      { zone: "Beauty", time: "16:30:28", dwell: 18, type: "SHELF" },
      { zone: "Exit", time: "16:31:02", dwell: 0, type: "EXIT" },
    ],
    totalDuration: 57,
  },
  {
    id: "store_1077_CAM1_T0042",
    label: "Customer #42",
    store: "Store 1077",
    type: "conversion",
    steps: [
      { zone: "Entrance", time: "17:45:22", dwell: 2, type: "ENTRANCE" },
      { zone: "Right Wall", time: "17:45:55", dwell: 48, type: "SHELF" },
      { zone: "Center Display 2", time: "17:46:58", dwell: 65, type: "DISPLAY" },
      { zone: "Left Wall", time: "17:48:15", dwell: 35, type: "SHELF" },
      { zone: "Billing", time: "17:49:05", dwell: 12, type: "BILLING" },
      { zone: "Exit", time: "17:49:32", dwell: 0, type: "EXIT" },
    ],
    totalDuration: 250,
  },
];

const STEP_COLORS: Record<string, { bg: string; text: string; glow: string }> = {
  ENTRANCE: { bg: "bg-emerald-500/20", text: "text-emerald-400", glow: "shadow-emerald-500/30" },
  SHELF: { bg: "bg-purple-500/20", text: "text-purple-400", glow: "shadow-purple-500/30" },
  DISPLAY: { bg: "bg-cyan-500/20", text: "text-cyan-400", glow: "shadow-cyan-500/30" },
  BILLING: { bg: "bg-amber-500/20", text: "text-amber-400", glow: "shadow-amber-500/30" },
  EXIT: { bg: "bg-gray-500/20", text: "text-gray-400", glow: "shadow-gray-500/30" },
};

const TYPE_BADGE: Record<string, { bg: string; text: string; label: string }> = {
  conversion: { bg: "bg-emerald-500/15", text: "text-emerald-400", label: "Conversion" },
  browse: { bg: "bg-cyan-500/15", text: "text-cyan-400", label: "Browse Only" },
  bounce: { bg: "bg-rose-500/15", text: "text-rose-400", label: "Bounce" },
};

export default function JourneyReplayPage() {
  const [selectedJourney, setSelectedJourney] = useState(0);
  const [activeStep, setActiveStep] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(false);

  const journey = JOURNEYS[selectedJourney];

  // Auto-play animation
  useEffect(() => {
    if (!isPlaying) return;
    if (activeStep >= journey.steps.length - 1) {
      setIsPlaying(false);
      return;
    }
    const timer = setTimeout(() => {
      setActiveStep((s) => s + 1);
    }, 1200);
    return () => clearTimeout(timer);
  }, [isPlaying, activeStep, journey.steps.length]);

  const handlePlay = () => {
    if (activeStep >= journey.steps.length - 1) {
      setActiveStep(-1);
    }
    setIsPlaying(true);
    if (activeStep < 0) setActiveStep(0);
  };

  return (
    <div className="min-h-screen gradient-mesh">
      <header className="sticky top-0 z-50 glass-card rounded-none border-x-0 border-t-0">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="p-2 rounded-lg hover:bg-[var(--bg-card)] transition-colors">
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <Route className="w-5 h-5 text-purple-400" />
            <div>
              <h1 className="text-base font-bold">Customer Journey Replay</h1>
              <p className="text-[10px] text-[var(--text-muted)]">Path Analysis & Visualization</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-[1400px] mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Journey Selector */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {JOURNEYS.map((j, i) => {
            const badge = TYPE_BADGE[j.type];
            return (
              <button key={j.id} onClick={() => { setSelectedJourney(i); setActiveStep(-1); setIsPlaying(false); }}
                className={cn(
                  "p-3 rounded-xl border text-left transition-all",
                  i === selectedJourney
                    ? "border-purple-500/50 bg-purple-500/10"
                    : "border-[var(--border-color)] bg-[var(--bg-card)] hover:border-purple-500/30"
                )}>
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-sm">{j.label}</span>
                  <span className={cn("px-2 py-0.5 rounded-full text-[10px] font-medium", badge.bg, badge.text)}>
                    {badge.label}
                  </span>
                </div>
                <div className="text-xs text-[var(--text-secondary)]">
                  {j.store} · {j.steps.length} steps · {formatDuration(j.totalDuration)}
                </div>
              </button>
            );
          })}
        </div>

        {/* Replay Controls */}
        <div className="glass-card p-5">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-lg font-bold">{journey.label}</h2>
              <p className="text-sm text-[var(--text-secondary)]">
                {journey.store} · {journey.steps.length} zones · Total: {formatDuration(journey.totalDuration)}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={handlePlay}
                className="p-2.5 rounded-xl bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 transition-colors">
                {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
              </button>
              <button onClick={() => { setActiveStep(-1); setIsPlaying(false); }}
                className="p-2.5 rounded-xl bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:text-white transition-colors">
                <SkipForward className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Timeline */}
          <div className="relative">
            {/* Progress bar */}
            <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-[var(--border-color)]">
              <div className="w-full bg-gradient-to-b from-purple-500 to-cyan-500 transition-all duration-500"
                style={{ height: `${activeStep >= 0 ? ((activeStep + 1) / journey.steps.length) * 100 : 0}%` }} />
            </div>

            {/* Steps */}
            <div className="space-y-1">
              {journey.steps.map((step, i) => {
                const colors = STEP_COLORS[step.type] || STEP_COLORS.SHELF;
                const isActive = i <= activeStep;
                const isCurrent = i === activeStep;

                return (
                  <div key={i}
                    className={cn(
                      "relative pl-14 py-3 rounded-xl transition-all duration-500 cursor-pointer",
                      isCurrent && "bg-[var(--bg-card)] shadow-lg",
                      isActive ? "opacity-100" : "opacity-40",
                    )}
                    onClick={() => { setActiveStep(i); setIsPlaying(false); }}
                  >
                    {/* Node */}
                    <div className={cn(
                      "absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 rounded-full border-2 transition-all duration-500 flex items-center justify-center",
                      isCurrent ? `${colors.bg} border-current ${colors.text} shadow-lg ${colors.glow} scale-125` :
                      isActive ? `${colors.bg} border-current ${colors.text}` :
                      "bg-[var(--bg-secondary)] border-[var(--border-color)]"
                    )}>
                      {isCurrent && <div className="w-2 h-2 rounded-full bg-current animate-pulse" />}
                    </div>

                    {/* Content */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className={cn("p-1.5 rounded-lg", colors.bg)}>
                          {step.type === "ENTRANCE" || step.type === "EXIT" ? (
                            <MapPin className={cn("w-4 h-4", colors.text)} />
                          ) : step.type === "BILLING" ? (
                            <ShoppingCart className={cn("w-4 h-4", colors.text)} />
                          ) : (
                            <MapPin className={cn("w-4 h-4", colors.text)} />
                          )}
                        </div>
                        <div>
                          <div className="font-semibold">{step.zone}</div>
                          <div className="text-xs text-[var(--text-secondary)]">
                            {step.type === "EXIT" ? "Left store" :
                             step.type === "BILLING" ? "Checkout queue" :
                             step.type === "ENTRANCE" ? "Entered store" :
                             `Browsing zone`}
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-mono text-[var(--text-secondary)]">{step.time}</div>
                        {step.dwell > 0 && (
                          <div className="text-xs text-[var(--text-muted)]">
                            <Clock className="w-3 h-3 inline mr-1" />
                            {formatDuration(step.dwell)}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Journey Statistics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="glass-card p-4 text-center">
            <div className="text-2xl font-bold text-purple-400">{journey.steps.length}</div>
            <div className="text-xs text-[var(--text-secondary)]">Zones Visited</div>
          </div>
          <div className="glass-card p-4 text-center">
            <div className="text-2xl font-bold text-amber-400">{formatDuration(journey.totalDuration)}</div>
            <div className="text-xs text-[var(--text-secondary)]">Total Duration</div>
          </div>
          <div className="glass-card p-4 text-center">
            <div className="text-2xl font-bold text-cyan-400">
              {formatDuration(journey.steps.reduce((s, st) => s + st.dwell, 0) / Math.max(journey.steps.filter(s => s.dwell > 0).length, 1))}
            </div>
            <div className="text-xs text-[var(--text-secondary)]">Avg Dwell per Zone</div>
          </div>
          <div className="glass-card p-4 text-center">
            <div className={cn("text-2xl font-bold", journey.type === "conversion" ? "text-emerald-400" : journey.type === "browse" ? "text-cyan-400" : "text-rose-400")}>
              {journey.type === "conversion" ? "Yes" : "No"}
            </div>
            <div className="text-xs text-[var(--text-secondary)]">Made Purchase</div>
          </div>
        </div>
      </main>
    </div>
  );
}
