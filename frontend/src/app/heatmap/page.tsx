"use client";

import { useState, useEffect, useRef } from "react";
import {
  Eye, ArrowLeft, Flame, Clock, Users, Zap,
} from "lucide-react";
import Link from "next/link";
import { cn, formatDuration } from "@/lib/utils";
import { CV_PIPELINE_RESULTS } from "@/lib/demo-data";

// ── Zone heatmap data (real CV + enriched) ──────────────────────
const STORE_1_ZONES = [
  { name: "Entrance", x: 2, y: 70, w: 13, h: 28, visits: 42, avgDwell: 4.4, type: "ENTRANCE", heat: 0.95 },
  { name: "Salm", x: 5, y: 2, w: 10, h: 12, visits: 8, avgDwell: 12.1, type: "SHELF", heat: 0.25 },
  { name: "TFS", x: 18, y: 2, w: 10, h: 12, visits: 6, avgDwell: 15.3, type: "SHELF", heat: 0.2 },
  { name: "Minimalist", x: 38, y: 2, w: 13, h: 12, visits: 14, avgDwell: 22.7, type: "SHELF", heat: 0.45 },
  { name: "Aqualogica", x: 53, y: 2, w: 12, h: 12, visits: 11, avgDwell: 18.4, type: "SHELF", heat: 0.35 },
  { name: "Foxtale", x: 67, y: 2, w: 10, h: 12, visits: 9, avgDwell: 14.2, type: "SHELF", heat: 0.3 },
  { name: "Juicy Chemistry", x: 79, y: 2, w: 11, h: 12, visits: 7, avgDwell: 19.8, type: "SHELF", heat: 0.22 },
  { name: "Faces Canada", x: 5, y: 82, w: 15, h: 16, visits: 24, avgDwell: 35.2, type: "SHELF", heat: 0.75 },
  { name: "Mars + NY Bae", x: 25, y: 82, w: 14, h: 16, visits: 18, avgDwell: 28.3, type: "SHELF", heat: 0.58 },
  { name: "Men's Section", x: 42, y: 82, w: 13, h: 16, visits: 10, avgDwell: 15.1, type: "SHELF", heat: 0.32 },
  { name: "L'Oreal", x: 58, y: 82, w: 18, h: 16, visits: 22, avgDwell: 42.8, type: "SHELF", heat: 0.7 },
  { name: "Beauty", x: 78, y: 82, w: 12, h: 16, visits: 12, avgDwell: 20.5, type: "SHELF", heat: 0.38 },
  { name: "Makeup Unit", x: 42, y: 30, w: 20, h: 25, visits: 16, avgDwell: 65.2, type: "DISPLAY", heat: 0.52 },
  { name: "Fragrance", x: 25, y: 30, w: 12, h: 20, visits: 8, avgDwell: 28.4, type: "DISPLAY", heat: 0.25 },
  { name: "Cash Counter", x: 85, y: 20, w: 13, h: 30, visits: 19, avgDwell: 6.6, type: "BILLING", heat: 0.6 },
];

const STORE_2_ZONES = [
  { name: "Entrance", x: 35, y: 85, w: 30, h: 13, visits: 68, avgDwell: 1.2, type: "ENTRANCE", heat: 1.0 },
  { name: "Left Wall", x: 2, y: 30, w: 13, h: 45, visits: 15, avgDwell: 22.4, type: "SHELF", heat: 0.42 },
  { name: "Right Wall", x: 85, y: 30, w: 13, h: 45, visits: 12, avgDwell: 18.7, type: "SHELF", heat: 0.35 },
  { name: "Center Disp 1", x: 25, y: 45, w: 20, h: 20, visits: 20, avgDwell: 32.1, type: "DISPLAY", heat: 0.58 },
  { name: "Center Disp 2", x: 55, y: 45, w: 20, h: 20, visits: 18, avgDwell: 28.6, type: "DISPLAY", heat: 0.52 },
  { name: "Makeup Area", x: 55, y: 22, w: 22, h: 20, visits: 14, avgDwell: 45.3, type: "DISPLAY", heat: 0.4 },
  { name: "Billing", x: 35, y: 10, w: 25, h: 15, visits: 47, avgDwell: 4.1, type: "BILLING", heat: 0.85 },
];

function heatColor(heat: number): string {
  if (heat > 0.8) return "rgba(239, 68, 68, 0.55)";
  if (heat > 0.6) return "rgba(249, 115, 22, 0.50)";
  if (heat > 0.4) return "rgba(245, 158, 11, 0.45)";
  if (heat > 0.2) return "rgba(34, 197, 94, 0.35)";
  return "rgba(59, 130, 246, 0.25)";
}

function heatBorder(heat: number): string {
  if (heat > 0.8) return "rgba(239, 68, 68, 0.8)";
  if (heat > 0.6) return "rgba(249, 115, 22, 0.7)";
  if (heat > 0.4) return "rgba(245, 158, 11, 0.6)";
  if (heat > 0.2) return "rgba(34, 197, 94, 0.5)";
  return "rgba(59, 130, 246, 0.4)";
}

export default function HeatmapPage() {
  const [activeStore, setActiveStore] = useState(0);
  const [hoveredZone, setHoveredZone] = useState<string | null>(null);
  const [showLabels, setShowLabels] = useState(true);

  const zones = activeStore === 0 ? STORE_1_ZONES : STORE_2_ZONES;
  const storeName = activeStore === 0 ? "Store 1076 — Mumbai" : "Store 1077 — Mumbai";

  const totalVisits = zones.reduce((s, z) => s + z.visits, 0);
  const hottest = [...zones].sort((a, b) => b.heat - a.heat)[0];
  const longestDwell = [...zones].sort((a, b) => b.avgDwell - a.avgDwell)[0];

  return (
    <div className="min-h-screen gradient-mesh">
      {/* Header */}
      <header className="sticky top-0 z-50 glass-card rounded-none border-x-0 border-t-0">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="p-2 rounded-lg hover:bg-[var(--bg-card)] transition-colors">
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <div className="w-8 h-8 rounded-lg gradient-purple flex items-center justify-center">
              <Flame className="w-4 h-4 text-white" />
            </div>
            <div>
              <h1 className="text-base font-bold">Store Layout Heatmap</h1>
              <p className="text-[10px] text-[var(--text-muted)]">Customer Movement Intelligence</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowLabels(!showLabels)}
              className={cn("px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors",
                showLabels ? "border-purple-500/50 bg-purple-500/10 text-purple-400" : "border-[var(--border-color)] text-[var(--text-secondary)]"
              )}
            >
              {showLabels ? "Labels On" : "Labels Off"}
            </button>
            <div className="flex rounded-lg border border-[var(--border-color)] overflow-hidden">
              {["Store 1", "Store 2"].map((label, i) => (
                <button key={i} onClick={() => setActiveStore(i)}
                  className={cn("px-3 py-1.5 text-xs font-medium transition-colors",
                    activeStore === i ? "bg-purple-500/20 text-purple-400" : "text-[var(--text-secondary)] hover:bg-[var(--bg-card)]"
                  )}>{label}</button>
              ))}
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-[1400px] mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* KPI Row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="stat-card bg-gradient-to-br from-rose-500/20 to-rose-600/5 border-rose-500/20">
            <Flame className="w-5 h-5 text-rose-400 mb-2" />
            <div className="text-2xl font-bold">{hottest.name}</div>
            <div className="text-sm text-[var(--text-secondary)]">Hottest Zone</div>
          </div>
          <div className="stat-card bg-gradient-to-br from-amber-500/20 to-amber-600/5 border-amber-500/20">
            <Clock className="w-5 h-5 text-amber-400 mb-2" />
            <div className="text-2xl font-bold">{formatDuration(longestDwell.avgDwell)}</div>
            <div className="text-sm text-[var(--text-secondary)]">Longest Dwell ({longestDwell.name})</div>
          </div>
          <div className="stat-card bg-gradient-to-br from-purple-500/20 to-purple-600/5 border-purple-500/20">
            <Users className="w-5 h-5 text-purple-400 mb-2" />
            <div className="text-2xl font-bold">{totalVisits}</div>
            <div className="text-sm text-[var(--text-secondary)]">Total Zone Visits</div>
          </div>
          <div className="stat-card bg-gradient-to-br from-cyan-500/20 to-cyan-600/5 border-cyan-500/20">
            <Zap className="w-5 h-5 text-cyan-400 mb-2" />
            <div className="text-2xl font-bold">{zones.length}</div>
            <div className="text-sm text-[var(--text-secondary)]">Active Zones</div>
          </div>
        </div>

        {/* Heatmap */}
        <div className="glass-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">{storeName}</h2>
            <div className="flex items-center gap-2 text-xs">
              <span className="text-[var(--text-muted)]">Cold</span>
              <div className="flex gap-0.5">
                {[0.1, 0.3, 0.5, 0.7, 0.9].map((h) => (
                  <div key={h} className="w-6 h-3 rounded-sm" style={{ background: heatColor(h) }} />
                ))}
              </div>
              <span className="text-[var(--text-muted)]">Hot</span>
            </div>
          </div>

          {/* Store Layout Canvas */}
          <div className="relative w-full bg-[#0d0d15] rounded-xl border border-[var(--border-color)] overflow-hidden"
            style={{ paddingBottom: "60%" }}>
            {/* Grid lines */}
            <div className="absolute inset-0 opacity-10" style={{
              backgroundImage: "linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px)",
              backgroundSize: "5% 5%",
            }} />

            {/* Store outline */}
            <div className="absolute inset-[3%] border border-dashed border-[var(--border-color)]/40 rounded-lg" />

            {/* Zone overlays */}
            {zones.map((zone) => (
              <div
                key={zone.name}
                className="absolute rounded-lg cursor-pointer transition-all duration-300"
                style={{
                  left: `${zone.x}%`, top: `${zone.y}%`,
                  width: `${zone.w}%`, height: `${zone.h}%`,
                  background: heatColor(zone.heat),
                  border: `2px solid ${heatBorder(zone.heat)}`,
                  boxShadow: hoveredZone === zone.name
                    ? `0 0 20px ${heatBorder(zone.heat)}, inset 0 0 20px ${heatColor(zone.heat)}`
                    : "none",
                  transform: hoveredZone === zone.name ? "scale(1.02)" : "scale(1)",
                  zIndex: hoveredZone === zone.name ? 10 : 1,
                }}
                onMouseEnter={() => setHoveredZone(zone.name)}
                onMouseLeave={() => setHoveredZone(null)}
              >
                {/* Zone Label */}
                {showLabels && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-1">
                    <span className="text-[10px] sm:text-xs font-semibold text-white drop-shadow-lg leading-tight">
                      {zone.name}
                    </span>
                    <span className="text-[9px] sm:text-[10px] text-white/70 mt-0.5">
                      {zone.visits} visits
                    </span>
                  </div>
                )}

                {/* Hover Tooltip */}
                {hoveredZone === zone.name && (
                  <div className="absolute -top-20 left-1/2 -translate-x-1/2 glass-card px-3 py-2 text-xs whitespace-nowrap z-50 shadow-xl">
                    <div className="font-semibold text-sm">{zone.name}</div>
                    <div className="text-[var(--text-secondary)] mt-1">
                      <span className="text-purple-400">{zone.visits}</span> visits |
                      Dwell: <span className="text-amber-400">{formatDuration(zone.avgDwell)}</span> |
                      Type: <span className="text-cyan-400">{zone.type}</span>
                    </div>
                  </div>
                )}
              </div>
            ))}

            {/* Movement flow arrows (decorative) */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-30" viewBox="0 0 100 60">
              <defs>
                <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="4" markerHeight="4" orient="auto">
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#a855f7" />
                </marker>
              </defs>
              {activeStore === 0 ? (
                <>
                  <path d="M 8,82 C 8,60 20,50 30,45" stroke="#a855f7" strokeWidth="0.4" fill="none" markerEnd="url(#arrow)" strokeDasharray="2,1" />
                  <path d="M 30,45 C 40,40 50,35 52,42" stroke="#a855f7" strokeWidth="0.3" fill="none" markerEnd="url(#arrow)" strokeDasharray="2,1" />
                  <path d="M 52,42 C 60,45 75,40 88,35" stroke="#10b981" strokeWidth="0.4" fill="none" markerEnd="url(#arrow)" strokeDasharray="2,1" />
                  <path d="M 12,82 C 15,75 20,85 25,88" stroke="#06b6d4" strokeWidth="0.3" fill="none" markerEnd="url(#arrow)" strokeDasharray="2,1" />
                  <path d="M 25,88 C 35,88 50,88 60,88" stroke="#06b6d4" strokeWidth="0.3" fill="none" markerEnd="url(#arrow)" strokeDasharray="2,1" />
                </>
              ) : (
                <>
                  <path d="M 50,90 C 50,70 35,55 30,50" stroke="#a855f7" strokeWidth="0.4" fill="none" markerEnd="url(#arrow)" strokeDasharray="2,1" />
                  <path d="M 50,90 C 50,70 65,55 65,50" stroke="#06b6d4" strokeWidth="0.4" fill="none" markerEnd="url(#arrow)" strokeDasharray="2,1" />
                  <path d="M 35,50 C 40,35 45,25 47,17" stroke="#10b981" strokeWidth="0.3" fill="none" markerEnd="url(#arrow)" strokeDasharray="2,1" />
                </>
              )}
            </svg>
          </div>
        </div>

        {/* Zone Rankings */}
        <div className="glass-card p-5">
          <h3 className="text-lg font-semibold mb-4">Zone Rankings by Traffic</h3>
          <div className="space-y-2">
            {[...zones].sort((a, b) => b.visits - a.visits).map((z, i) => {
              const maxVisits = zones.reduce((m, z) => Math.max(m, z.visits), 1);
              const pct = (z.visits / maxVisits) * 100;
              return (
                <div key={z.name} className="flex items-center gap-3">
                  <span className="w-6 text-sm text-[var(--text-muted)] text-right">{i + 1}</span>
                  <div className="w-28 text-sm truncate">{z.name}</div>
                  <div className="flex-1 progress-bar">
                    <div className="progress-fill" style={{
                      width: `${pct}%`,
                      background: heatColor(z.heat),
                    }} />
                  </div>
                  <span className="w-12 text-right text-sm font-medium">{z.visits}</span>
                  <span className="w-16 text-right text-xs text-[var(--text-secondary)]">{formatDuration(z.avgDwell)}</span>
                </div>
              );
            })}
          </div>
        </div>
      </main>
    </div>
  );
}
