"use client";

import { useEffect, useRef } from "react";
import { useDashboard } from "@/components/dashboard";
import { FilterBar } from "@/components/filters";
import { Card, CardTitle, Empty, ErrorState, Loading, Note, PageHeader, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import type { CameraHeatmap, HeatmapResponse } from "@/lib/types";
import { fmtDuration, fmtInt } from "@/lib/utils";

// Cool -> hot ramp; alpha grows with intensity so quiet floor stays visible.
const RAMP: [number, number, number][] = [
  [59, 130, 246], [34, 197, 94], [234, 179, 8], [249, 115, 22], [239, 68, 68],
];

function rampColour(v: number): [number, number, number] {
  const x = Math.min(1, Math.max(0, v)) * (RAMP.length - 1);
  const i = Math.min(RAMP.length - 2, Math.floor(x));
  const f = x - i;
  const a = RAMP[i], b = RAMP[i + 1];
  return [0, 1, 2].map((k) => Math.round(a[k] + (b[k] - a[k]) * f)) as [number, number, number];
}

function HeatLayer({ cam }: { cam: CameraHeatmap }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const img = ctx.createImageData(cam.cols, cam.rows);
    // Square-root scale: a spot people pass through still shows next to
    // the one place everybody stands.
    const max = Math.sqrt(cam.max_cell_seconds || 1);
    for (const [cell, secs] of cam.cells) {
      const v = Math.sqrt(secs) / max;
      const [r, g, b] = rampColour(v);
      const o = cell * 4;
      img.data[o] = r; img.data[o + 1] = g; img.data[o + 2] = b;
      img.data[o + 3] = Math.round(70 + 170 * v);
    }
    ctx.putImageData(img, 0, 0);
  }, [cam]);
  return (
    <canvas ref={ref} width={cam.cols} height={cam.rows} aria-hidden
      className="absolute inset-0 h-full w-full" style={{ filter: "blur(10px)", imageRendering: "auto" }} />
  );
}

function CameraCard({ cam }: { cam: CameraHeatmap }) {
  return (
    <Card>
      <CardTitle title={`${cam.camera_code} · ${cam.name}`}
        hint={`${fmtInt(cam.videos)} video${cam.videos === 1 ? "" : "s"}, ${fmtDuration(cam.seconds_analysed)} analysed`} />
      <div className="relative w-full overflow-hidden rounded-lg bg-black" style={{ aspectRatio: `${cam.cols} / ${cam.rows}` }}>
        {cam.has_reference_frame && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={`/api/cameras/${cam.camera_id}/reference-frame`} alt={`Camera ${cam.camera_code}`}
            className="absolute inset-0 h-full w-full object-fill opacity-70" />
        )}
        <HeatLayer cam={cam} />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3">
        <Stat label="Shoppers seen" value={fmtInt(cam.shoppers)} />
        <Stat label="Time people spent here" value={fmtDuration(cam.person_seconds)} />
      </div>
    </Card>
  );
}

export default function HeatmapPage() {
  const d = useDashboard();
  const key = d.store ? `hm:${d.store.id}:${d.start}:${d.end}:${d.data}` : null;
  const hm = useResource(key, (signal) =>
    api<HeatmapResponse>(`/api/analytics/${d.store!.id}/heatmap`, { query: d.query, signal }));

  return (
    <>
      <PageHeader title="Heatmap" subtitle="Where shoppers stood and lingered, on each camera's picture" />
      <FilterBar />
      {hm.error && <ErrorState error={hm.error} onRetry={hm.reload} />}
      {hm.loading && !hm.data && <Loading />}
      {hm.data && (
        hm.data.cameras.length === 0 ? (
          <Empty title="No heatmap for this range">
            Heatmaps come from processed camera videos. Upload a recording on the Videos page.
          </Empty>
        ) : (
          <div className="space-y-4">
            <Note>
              Colour shows how long people stood at each spot (their feet position), red the longest. It is
              counted from processed videos only. Shoppers are counted once per visit, also when they leave the
              picture and come back.
            </Note>
            <div className="grid gap-4 lg:grid-cols-2">
              {hm.data.cameras.map((c) => <CameraCard key={c.camera_id} cam={c} />)}
            </div>
          </div>
        )
      )}
    </>
  );
}
