"use client";

import { useEffect, useRef } from "react";

/**
 * Animated illustration of a store floor seen from above. Shoppers are drawn
 * as anonymous dots that walk in through the entry line, browse zones and
 * queue at billing. Nothing here is customer data; the panel says so.
 */

type Walker = { path: string; dur: number; begin: number; color: string };

const WALKERS: Walker[] = [
  // entrance -> staples -> billing
  { path: "M70 372 L70 330 L120 300 L120 190 L170 150 L250 150 L420 170 L470 250 L470 300", dur: 14, begin: 0, color: "#5ef0b4" },
  // entrance -> promo endcap -> personal care -> billing
  { path: "M86 372 L86 320 L200 300 L260 280 L300 220 L330 120 L400 110 L470 210 L490 300", dur: 17, begin: 2.5, color: "#5ef0b4" },
  // entrance -> snacks -> leaves without buying
  { path: "M78 372 L80 310 L150 260 L230 230 L250 180 L200 250 L120 320 L76 372", dur: 13, begin: 5, color: "#ffb35c" },
  // browses personal care for a long time
  { path: "M70 372 L74 300 L180 270 L320 140 L360 120 L340 100 L370 130 L345 110 L430 180 L450 300", dur: 19, begin: 8, color: "#5ef0b4" },
  // quick visit to staples, billing
  { path: "M82 372 L84 330 L110 240 L130 170 L200 160 L300 180 L440 230 L510 300", dur: 12, begin: 10.5, color: "#5ef0b4" },
];

export function StoreFloor() {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg || typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => (mq.matches ? svg.pauseAnimations() : svg.unpauseAnimations());
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  return (
    <svg
      ref={svgRef}
      viewBox="0 0 560 400"
      role="img"
      aria-label="Illustration: a store floor from above. Anonymous dots enter through the door, visit aisles and queue at billing."
      className="h-auto w-full"
    >
      <defs>
        <pattern id="ft-grid" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M20 0H0V20" fill="none" stroke="#ffffff" strokeOpacity="0.04" />
        </pattern>
        <radialGradient id="ft-glow" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#5ef0b4" stopOpacity="0.55" />
          <stop offset="1" stopColor="#5ef0b4" stopOpacity="0" />
        </radialGradient>
      </defs>

      <rect width="560" height="400" fill="#15121f" />
      <rect width="560" height="400" fill="url(#ft-grid)" />

      {/* Walls with the door gap bottom-left */}
      <path d="M40 372 V30 H530 V372 H110" fill="none" stroke="#3a3550" strokeWidth="3" />

      {/* Zones */}
      <g fontFamily="inherit" fontSize="10" fontWeight="600" letterSpacing="0.06em">
        <rect x="100" y="140" width="60" height="120" rx="6" fill="#6c5cff" fillOpacity="0.14" stroke="#8b7dff" strokeOpacity="0.5" strokeDasharray="4 3" />
        <text x="106" y="134" fill="#b3a9ff">STAPLES</text>

        <rect x="200" y="170" width="80" height="80" rx="6" fill="#6c5cff" fillOpacity="0.14" stroke="#8b7dff" strokeOpacity="0.5" strokeDasharray="4 3" />
        <text x="206" y="164" fill="#b3a9ff">SNACKS</text>

        <rect x="300" y="60" width="110" height="80" rx="6" fill="#6c5cff" fillOpacity="0.14" stroke="#8b7dff" strokeOpacity="0.5" strokeDasharray="4 3" />
        <text x="306" y="54" fill="#b3a9ff">PERSONAL CARE</text>

        <rect x="180" y="270" width="110" height="44" rx="6" fill="#ff7ab6" fillOpacity="0.12" stroke="#ff7ab6" strokeOpacity="0.5" strokeDasharray="4 3" />
        <text x="186" y="330" fill="#ff9cc8">PROMO ENDCAP</text>

        <rect x="440" y="200" width="80" height="120" rx="6" fill="#ffb35c" fillOpacity="0.12" stroke="#ffb35c" strokeOpacity="0.55" strokeDasharray="4 3" />
        <text x="446" y="194" fill="#ffc985">BILLING QUEUE</text>
        <rect x="455" y="330" width="60" height="14" rx="3" fill="#3a3550" />
      </g>

      {/* Entry line at the door */}
      <line x1="44" y1="360" x2="108" y2="360" stroke="#5ef0b4" strokeWidth="2" strokeDasharray="5 4" />
      <text x="46" y="388" fontSize="10" fontWeight="600" fill="#5ef0b4" letterSpacing="0.06em">ENTRY LINE</text>

      {/* Camera icons */}
      {[[48, 40], [522, 40], [522, 150]].map(([x, y]) => (
        <g key={`${x}-${y}`} transform={`translate(${x} ${y})`}>
          <circle r="7" fill="#2a2540" stroke="#6b6487" />
          <circle r="2.5" fill="#ff5d73">
            <animate attributeName="opacity" values="1;0.2;1" dur="2s" repeatCount="indefinite" />
          </circle>
        </g>
      ))}

      {/* Shoppers: faint journey line plus the moving dot */}
      {WALKERS.map((w, i) => (
        <g key={i}>
          <path d={w.path} fill="none" stroke={w.color} strokeOpacity="0.09" strokeWidth="2" strokeLinejoin="round" />
          <g opacity="0">
            <animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.04;0.94;1" dur={`${w.dur}s`} begin={`${w.begin}s`} repeatCount="indefinite" />
            <circle r="14" fill="url(#ft-glow)" />
            <circle r="5" fill={w.color} stroke="#15121f" strokeWidth="2" />
            <animateMotion path={w.path} dur={`${w.dur}s`} begin={`${w.begin}s`} repeatCount="indefinite" rotate="0" />
          </g>
        </g>
      ))}
    </svg>
  );
}
