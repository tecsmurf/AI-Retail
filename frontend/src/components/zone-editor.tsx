"use client";

import { useEffect, useRef, useState } from "react";
import { ImageUp, Plus, Trash2, Undo2 } from "lucide-react";
import { api } from "@/lib/api";
import type { Camera, CameraConfig, EntryLine, Point, ZoneType } from "@/lib/types";
import { ZONE_TYPES } from "@/lib/types";
import { ZONE_COLORS, cn } from "@/lib/utils";
import { Button, ErrorState, Field, Note, inputClass } from "./ui";

interface DraftZone {
  zone_code: string;
  name: string;
  zone_type: ZoneType;
  polygon: Point[];
  priority: number;
}

type Mode = { kind: "idle" } | { kind: "zone"; index: number } | { kind: "line"; points: Point[] };

const round = (v: number) => Math.round(Math.min(1, Math.max(0, v)) * 10000) / 10000;

/**
 * Draw zones (polygons) and the entry line on the camera's reference frame.
 * Coordinates are normalized (0..1 from the top-left), so they work for any
 * resolution the camera records at. People are placed by the bottom-centre of
 * their box (where the feet are), so draw zones on the floor area.
 */
export function ZoneEditor({ camera, onSaved }: { camera: Camera; onSaved: (c: Camera) => void }) {
  const [zones, setZones] = useState<DraftZone[] | null>(null);
  const [line, setLine] = useState<EntryLine | null>(null);
  const [mode, setMode] = useState<Mode>({ kind: "idle" });
  const [selected, setSelected] = useState<number | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [imgVersion, setImgVersion] = useState(0);
  const [hasFrame, setHasFrame] = useState(camera.has_reference_frame);
  const svgRef = useRef<SVGSVGElement>(null);
  const drag = useRef<{ zone: number; vertex: number } | null>(null);
  const allowLine = camera.camera_type === "entrance" || camera.camera_type === "other";

  useEffect(() => {
    let alive = true;
    api<CameraConfig>(`/api/cameras/${camera.id}/config`).then(
      (cfg) => {
        if (!alive) return;
        setZones(cfg.zones.filter((z) => z.polygon && z.polygon.length >= 3).map((z) => ({
          zone_code: z.zone_code, name: z.name, zone_type: z.zone_type, polygon: z.polygon as Point[], priority: z.priority,
        })));
        setLine(cfg.camera.entry_line);
      },
      (e) => alive && setError(e),
    );
    return () => { alive = false; };
  }, [camera.id]);

  function toPoint(e: React.PointerEvent): Point {
    const r = svgRef.current!.getBoundingClientRect();
    return [round((e.clientX - r.left) / r.width), round((e.clientY - r.top) / r.height)];
  }

  function onCanvasDown(e: React.PointerEvent) {
    if (!zones) return;
    const p = toPoint(e);
    setSaved(false);
    if (mode.kind === "zone") {
      setZones(zones.map((z, i) => (i === mode.index ? { ...z, polygon: [...z.polygon, p] } : z)));
    } else if (mode.kind === "line") {
      const pts = [...mode.points, p];
      if (pts.length === 2) {
        setLine({ p1: pts[0], p2: pts[1], inside: line?.inside ?? "right" });
        setMode({ kind: "idle" });
      } else setMode({ kind: "line", points: pts });
    }
  }

  function onMove(e: React.PointerEvent) {
    if (!drag.current || !zones) return;
    const p = toPoint(e);
    const { zone, vertex } = drag.current;
    setZones(zones.map((z, i) => (i === zone ? { ...z, polygon: z.polygon.map((q, j) => (j === vertex ? p : q)) } : z)));
  }

  function addZone() {
    if (!zones) return;
    const n = zones.length + 1;
    const z: DraftZone = { zone_code: `Z${Date.now().toString(36).slice(-5).toUpperCase()}`, name: `Zone ${n}`, zone_type: "SHELF", polygon: [], priority: 0 };
    setZones([...zones, z]);
    setSelected(zones.length);
    setMode({ kind: "zone", index: zones.length });
    setSaved(false);
  }

  function patch(i: number, p: Partial<DraftZone>) {
    setZones(zones!.map((z, j) => (j === i ? { ...z, ...p } : z)));
    setSaved(false);
  }

  async function save() {
    if (!zones) return;
    const incomplete = zones.find((z) => z.polygon.length < 3);
    if (incomplete) {
      setError(new Error(`"${incomplete.name}" needs at least 3 points.`));
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const cfg = await api<CameraConfig>(`/api/cameras/${camera.id}/config`, {
        method: "PUT",
        json: { zones: zones.map((z) => ({ ...z, name: z.name.trim() })), entry_line: allowLine ? line : null },
      });
      setMode({ kind: "idle" });
      setSaved(true);
      onSaved(cfg.camera);
    } catch (e) {
      setError(e);
    } finally {
      setSaving(false);
    }
  }

  async function uploadFrame(file: File) {
    const form = new FormData();
    form.append("file", file);
    try {
      await api(`/api/cameras/${camera.id}/reference-frame`, { method: "POST", body: form });
      setHasFrame(true);
      setImgVersion((v) => v + 1);
    } catch (e) {
      setError(e);
    }
  }

  const aspect = camera.reference_frame_width && camera.reference_frame_height
    ? `${camera.reference_frame_width} / ${camera.reference_frame_height}` : "16 / 9";
  const hint = mode.kind === "zone"
    ? "Tap the image to add corners of the zone, then press Done."
    : mode.kind === "line" ? `Tap the ${mode.points.length === 0 ? "start" : "end"} of the entry line.` : null;

  return (
    <div className="space-y-3">
      <div className="relative w-full overflow-hidden rounded-xl border border-[var(--border-color)] bg-black" style={{ aspectRatio: aspect }}>
        {hasFrame ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={`/api/cameras/${camera.id}/reference-frame?v=${imgVersion}`} alt={`Reference frame for ${camera.camera_code}`}
            className="absolute inset-0 h-full w-full object-fill select-none" draggable={false} />
        ) : (
          <div className="absolute inset-0 grid place-items-center p-6 text-center text-xs text-[var(--text-muted)]">
            No reference frame yet. Process one recording from this camera (a frame is saved automatically) or upload a still image.
          </div>
        )}
        <svg ref={svgRef} viewBox="0 0 1 1" preserveAspectRatio="none"
          className={cn("absolute inset-0 h-full w-full touch-none", mode.kind !== "idle" && "cursor-crosshair")}
          onPointerDown={onCanvasDown} onPointerMove={onMove} onPointerUp={() => { drag.current = null; }}
          onPointerLeave={() => { drag.current = null; }}>
          {zones?.map((z, i) => {
            const color = ZONE_COLORS[z.zone_type] ?? "#a855f7";
            const pts = z.polygon.map((p) => p.join(",")).join(" ");
            return (
              <g key={z.zone_code} onPointerDown={(e) => { if (mode.kind === "idle") { e.stopPropagation(); setSelected(i); } }}>
                {z.polygon.length >= 3
                  ? <polygon points={pts} fill={color} fillOpacity={selected === i ? 0.35 : 0.2} stroke={color} strokeWidth={selected === i ? 3 : 2} vectorEffect="non-scaling-stroke" />
                  : <polyline points={pts} fill="none" stroke={color} strokeWidth={2} strokeDasharray="4 3" vectorEffect="non-scaling-stroke" />}
                {(selected === i || (mode.kind === "zone" && mode.index === i)) && z.polygon.map((p, j) => (
                  <circle key={j} cx={p[0]} cy={p[1]} r={0.012} fill="white" stroke={color} strokeWidth={2} vectorEffect="non-scaling-stroke"
                    onPointerDown={(e) => { e.stopPropagation(); (e.target as Element).setPointerCapture?.(e.pointerId); drag.current = { zone: i, vertex: j }; }} />
                ))}
              </g>
            );
          })}
          {allowLine && line && <LineGlyph line={line} />}
          {mode.kind === "line" && mode.points.map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r={0.012} fill="#f43f5e" />)}
        </svg>
      </div>
      {hint && <p className="text-xs text-purple-200">{hint}</p>}

      <div className="flex flex-wrap gap-2">
        {mode.kind === "zone" ? (
          <>
            <Button variant="primary" onClick={() => setMode({ kind: "idle" })}>Done</Button>
            <Button onClick={() => patch(mode.index, { polygon: zones![mode.index].polygon.slice(0, -1) })}><Undo2 className="h-4 w-4" /> Undo point</Button>
          </>
        ) : (
          <Button onClick={addZone} disabled={!zones}><Plus className="h-4 w-4" /> Add zone</Button>
        )}
        {allowLine && mode.kind !== "zone" && (
          <Button onClick={() => setMode({ kind: "line", points: [] })}>{line ? "Redraw entry line" : "Draw entry line"}</Button>
        )}
        <label className="inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-lg px-3 text-sm hover:bg-white/5">
          <ImageUp className="h-4 w-4" /> Upload still image
          <input type="file" accept="image/jpeg,image/png" className="sr-only" onChange={(e) => e.target.files?.[0] && void uploadFrame(e.target.files[0])} />
        </label>
      </div>

      {allowLine && line && (
        <div className="card flex flex-wrap items-center gap-3 p-3 text-sm">
          <span>Inside the store is the</span>
          <select className={cn(inputClass, "w-auto")} value={line.inside} onChange={(e) => { setLine({ ...line, inside: e.target.value as "left" | "right" }); setSaved(false); }}>
            <option value="right">right side (walking from start to end)</option>
            <option value="left">left side (walking from start to end)</option>
          </select>
          <span className="text-xs text-[var(--text-muted)]">The short arrow points into the store; flip it if it points outside.</span>
          <Button variant="ghost" onClick={() => { setLine(null); setSaved(false); }}>Remove line</Button>
        </div>
      )}

      {zones && zones.length > 0 && (
        <ul className="space-y-2">
          {zones.map((z, i) => (
            <li key={z.zone_code} className={cn("card grid gap-2 p-3 sm:grid-cols-[1fr_10rem_6rem_auto]", selected === i && "border-purple-500/60")}
              onClick={() => setSelected(i)}>
              <Field label="Name"><input className={inputClass} value={z.name} onChange={(e) => patch(i, { name: e.target.value })} /></Field>
              <Field label="Type">
                <select className={inputClass} value={z.zone_type} onChange={(e) => patch(i, { zone_type: e.target.value as ZoneType })}>
                  {ZONE_TYPES.map((t) => <option key={t} value={t}>{t.toLowerCase()}</option>)}
                </select>
              </Field>
              <Field label="Priority"><input className={inputClass} type="number" value={z.priority} onChange={(e) => patch(i, { priority: Number(e.target.value) || 0 })} /></Field>
              <div className="flex items-end gap-1">
                <Button variant="ghost" onClick={(e) => { e.stopPropagation(); setSelected(i); setMode({ kind: "zone", index: i }); }}>Add points</Button>
                <Button variant="ghost" aria-label={`Delete ${z.name}`} onClick={(e) => { e.stopPropagation(); setZones(zones.filter((_, j) => j !== i)); setSelected(null); setSaved(false); }}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
              <span className="text-xs text-[var(--text-muted)] sm:col-span-4">{z.polygon.length} points · drag the white dots on the image to adjust</span>
            </li>
          ))}
        </ul>
      )}

      <Note>
        A person counts as inside a zone when the bottom-centre of their box (their feet) is inside it. Where zones overlap, higher
        priority wins, then the smaller zone. Use QUEUE for the waiting line and BILLING for the counter on billing cameras.
        Saving creates a new configuration version; recordings already processed keep their results until you re-process them.
      </Note>
      {error !== null && <ErrorState error={error} />}
      <div className="flex items-center gap-3">
        <Button variant="primary" onClick={() => void save()} disabled={saving || !zones || mode.kind !== "idle"}>
          {saving ? "Saving…" : "Save zones"}
        </Button>
        {saved && <span className="text-sm text-emerald-300">Saved</span>}
      </div>
    </div>
  );
}

function LineGlyph({ line }: { line: EntryLine }) {
  const [x1, y1] = line.p1;
  const [x2, y2] = line.p2;
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = Math.hypot(dx, dy) || 1;
  // Right-hand normal in screen coordinates (y down).
  const s = line.inside === "right" ? 1 : -1;
  const nx = (-dy / len) * 0.08 * s;
  const ny = (dx / len) * 0.08 * s;
  return (
    <g>
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#f43f5e" strokeWidth={3} vectorEffect="non-scaling-stroke" />
      <line x1={mx} y1={my} x2={mx + nx} y2={my + ny} stroke="#f43f5e" strokeWidth={2} vectorEffect="non-scaling-stroke" />
      <circle cx={mx + nx} cy={my + ny} r={0.012} fill="#f43f5e" />
    </g>
  );
}
