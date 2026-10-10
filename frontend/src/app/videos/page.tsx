"use client";

import { useRef, useState } from "react";
import { CheckCircle2, CircleAlert, Loader2, Upload, XCircle } from "lucide-react";
import { useDashboard } from "@/components/dashboard";
import { useSession } from "@/components/session";
import { Badge, Button, Card, CardTitle, Empty, ErrorState, Field, Loading, Note, PageHeader, inputClass } from "@/components/ui";
import { api, uploadFile } from "@/lib/api";
import { useInterval, useResource } from "@/lib/hooks";
import type { Camera, Job, JobPage, VideoCreated } from "@/lib/types";
import { cn, fmtBytes, fmtDateTime, fmtDuration, relativeTime } from "@/lib/utils";

const STATUS_TONE = { queued: "neutral", running: "info", completed: "good", failed: "bad", cancelled: "warn" } as const;

export default function VideosPage() {
  const d = useDashboard();
  const { isAdmin } = useSession();
  const store = d.store;
  const cams = useResource(store ? `cams:${store.id}` : null, (signal) => api<Camera[]>(`/api/stores/${store!.id}/cameras`, { signal }));
  const jobs = useResource(store ? `jobs:${store.id}` : null, (signal) =>
    api<JobPage>("/api/jobs", { query: { store_id: store!.id, limit: 50 }, signal }));
  const active = jobs.data?.items.some((j) => j.status === "queued" || j.status === "running");
  useInterval(jobs.reload, active ? 4000 : 30000);
  const [openJob, setOpenJob] = useState<string | null>(null);

  return (
    <>
      <PageHeader title="Videos" subtitle="Upload recordings and follow their processing" />
      {d.stores && d.stores.length > 1 && (
        <select aria-label="Store" value={store?.id ?? ""} onChange={(e) => d.setStore(e.target.value)} className={cn(inputClass, "mb-4 sm:w-64")}>
          {d.stores.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      )}
      <div className="grid gap-4 lg:grid-cols-5">
        <div className="min-w-0 lg:col-span-2">
          {isAdmin ? (
            cams.data ? <UploadCard cameras={cams.data} storeId={store!.id} onQueued={jobs.reload} />
              : cams.error ? <ErrorState error={cams.error} onRetry={cams.reload} /> : <Loading />
          ) : (
            <Card><Note>Only administrators can upload recordings.</Note></Card>
          )}
        </div>
        <div className="min-w-0 lg:col-span-3">
          <Card>
            <CardTitle title="Processing jobs" hint={active ? "Refreshing every few seconds" : undefined} />
            {jobs.error && <ErrorState error={jobs.error} onRetry={jobs.reload} />}
            {jobs.loading && !jobs.data && <Loading />}
            {jobs.data && (jobs.data.items.length === 0 ? <Empty title="No recordings processed for this store yet" /> : (
              <ul className="divide-y divide-[var(--border-color)]">
                {jobs.data.items.map((j) => (
                  <JobRow key={j.id} job={j} tz={store?.timezone} open={openJob === j.id} isAdmin={isAdmin}
                    onToggle={() => setOpenJob(openJob === j.id ? null : j.id)} onChanged={jobs.reload} />
                ))}
              </ul>
            ))}
          </Card>
        </div>
      </div>
    </>
  );
}

function UploadCard({ cameras, storeId, onQueued }: { cameras: Camera[]; storeId: string; onQueued: () => void }) {
  const [cameraId, setCameraId] = useState(cameras[0]?.id ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [recorded, setRecorded] = useState("");
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState<string | null>(null);
  const abortRef = useRef<(() => void) | null>(null);
  const camera = cameras.find((c) => c.id === cameraId);

  if (cameras.length === 0) {
    return <Card><Empty title="Add a camera first">Each recording belongs to one camera, whose zones decide what is measured.</Empty></Card>;
  }

  async function start() {
    if (!file || !cameraId) return;
    setError(null);
    setDone(null);
    setProgress(0);
    try {
      const recordedStart = recorded ? new Date(recorded).toISOString() : undefined;
      const created = await api<VideoCreated>("/api/videos", {
        json: { store_id: storeId, camera_id: cameraId, filename: file.name, size_bytes: file.size,
          content_type: file.type || "video/mp4", recorded_start: recordedStart },
      });
      const up = uploadFile(created.upload.url, file, created.upload.headers, created.upload.direct_to_storage, setProgress);
      abortRef.current = up.abort;
      await up.promise;
      const job = await api<Job>(`/api/videos/${created.video.id}/complete`, { json: { start_processing: true } });
      setDone(`Queued for processing (${job.camera_code}).`);
      setFile(null);
      onQueued();
    } catch (e) {
      setError(e);
    } finally {
      setProgress(null);
      abortRef.current = null;
    }
  }

  const noZones = camera && camera.camera_type !== "entrance" && camera.config_version <= 1;
  const noLine = camera && camera.camera_type === "entrance" && !camera.entry_line;

  return (
    <Card>
      <CardTitle title="Upload a recording" hint="MP4, MOV, MKV, AVI or WebM · up to 2 GB" />
      <div className="space-y-3">
        <Field label="Camera">
          <select className={inputClass} value={cameraId} onChange={(e) => setCameraId(e.target.value)}>
            {cameras.map((c) => <option key={c.id} value={c.id}>{c.camera_code} · {c.name} ({c.camera_type})</option>)}
          </select>
        </Field>
        {(noZones || noLine) && (
          <Note>
            {noLine ? "This entrance camera has no entry line yet, so no entries/exits will be counted. " : "This camera has no zones yet, so no zone or queue events will be produced. "}
            Set them up under Cameras &amp; zones first.
          </Note>
        )}
        <Field label="Recording started at" hint="Your device's time zone. Leave empty to use the upload time (marked as an assumption).">
          <input type="datetime-local" step="1" className={inputClass} value={recorded} onChange={(e) => setRecorded(e.target.value)} />
        </Field>
        <label className={cn("flex min-h-24 cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border border-dashed border-[var(--border-hover)] p-4 text-center text-sm",
          file && "border-purple-500/60")}>
          <Upload className="h-5 w-5 text-[var(--text-muted)]" />
          {file ? <span>{file.name} · {fmtBytes(file.size)}</span> : <span className="text-[var(--text-secondary)]">Choose a video file</span>}
          <input type="file" accept="video/*,.mkv,.avi" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        {progress !== null ? (
          <div>
            <div className="mb-1 flex justify-between text-xs text-[var(--text-secondary)]">
              <span>Uploading…</span><span className="tabular-nums">{Math.round(progress * 100)}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/5"><div className="h-full bg-purple-500 transition-all" style={{ width: `${progress * 100}%` }} /></div>
            <Button variant="ghost" className="mt-2" onClick={() => abortRef.current?.()}>Cancel upload</Button>
          </div>
        ) : (
          <Button variant="primary" className="w-full" disabled={!file} onClick={() => void start()}>Upload and process</Button>
        )}
        {error !== null && <ErrorState error={error} />}
        {done && <p className="flex items-center gap-2 text-sm text-emerald-300"><CheckCircle2 className="h-4 w-4" /> {done}</p>}
        <Note>Keep this page open until the upload reaches 100%. Processing then runs on the server; you can close the page.</Note>
      </div>
    </Card>
  );
}

function JobRow({ job: j, tz, open, isAdmin, onToggle, onChanged }: {
  job: Job; tz?: string; open: boolean; isAdmin: boolean; onToggle: () => void; onChanged: () => void;
}) {
  const [err, setErr] = useState<unknown>(null);
  const r = j.results;
  async function act(path: string, json?: unknown) {
    setErr(null);
    try {
      await api(path, { method: "POST", json });
      onChanged();
    } catch (e) {
      setErr(e);
    }
  }
  const Icon = j.status === "completed" ? CheckCircle2 : j.status === "failed" ? CircleAlert : j.status === "cancelled" ? XCircle : Loader2;
  return (
    <li className="py-3">
      <button className="flex w-full items-start gap-3 text-left" onClick={onToggle} aria-expanded={open}>
        <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", j.status === "running" && "animate-spin text-cyan-300",
          j.status === "completed" && "text-emerald-300", j.status === "failed" && "text-rose-300")} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate text-sm font-medium">{j.video_filename ?? "video"}</span>
            <Badge tone={STATUS_TONE[j.status]}>{j.status}</Badge>
            {r?.superseded_by && <Badge tone="warn">replaced by a newer run</Badge>}
          </div>
          <div className="mt-0.5 text-xs text-[var(--text-muted)]">
            {j.camera_code} · created {relativeTime(j.created_at)}
            {j.status === "completed" && r && ` · ${r.event_total ?? 0} events · ${r.tracks_created ?? 0} tracks`}
            {j.status === "failed" && j.error_code && ` · ${j.error_code}`}
          </div>
          {(j.status === "running" || j.status === "queued") && (
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/5">
              <div className="h-full bg-cyan-400 transition-all" style={{ width: `${Math.max(2, j.progress * 100)}%` }} />
            </div>
          )}
        </div>
      </button>
      {open && (
        <div className="mt-3 space-y-3 pl-7 text-sm">
          {j.error_message && <p className="rounded-lg bg-rose-500/5 p-2 text-rose-200">{j.error_message}</p>}
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-3">
            <Info k="Stage" v={j.stage ?? "—"} />
            <Info k="Attempts" v={`${j.attempts} / ${j.max_attempts}`} />
            <Info k="Started" v={fmtDateTime(j.started_at, tz)} />
            <Info k="Finished" v={fmtDateTime(j.finished_at, tz)} />
            {r?.video && <Info k="Video" v={`${r.video.width}×${r.video.height} · ${r.video.fps?.toFixed(1)} fps · ${fmtDuration(r.video.duration_s)}`} />}
            {r?.processing_seconds !== undefined && <Info k="Processing" v={`${fmtDuration(r.processing_seconds)} (${r.realtime_factor ?? "—"}× real time)`} />}
            {r?.frames_analyzed !== undefined && <Info k="Frames analysed" v={String(r.frames_analyzed)} />}
            {r?.max_people_in_frame !== undefined && <Info k="Max people in a frame" v={String(r.max_people_in_frame)} />}
            {j.model_name && <Info k="Model" v={`${j.model_name} · ${j.model_sha256?.slice(0, 10)}…`} />}
          </dl>
          {r?.events && Object.keys(r.events).length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(r.events).map(([k, v]) => <Badge key={k}>{k.replace(/_/g, " ").toLowerCase()}: {v}</Badge>)}
            </div>
          )}
          {r?.recorded_start_assumed && <Note>Recording start time was not given; the upload time was used, so hours of day may be wrong.</Note>}
          {r?.warnings?.map((w) => <Note key={w}>{w}</Note>)}
          {j.artifacts?.snapshots && j.artifacts.snapshots.length > 0 && (
            <div>
              <div className="mb-1 text-xs text-[var(--text-muted)]">Detections and tracks (sampled frames)</div>
              <div className="flex gap-2 overflow-x-auto pb-1">
                {j.artifacts.snapshots.map((key) => {
                  const name = key.split("/").pop()!;
                  return (
                    <a key={key} href={`/api/jobs/${j.id}/artifacts/${name}`} target="_blank" rel="noreferrer" className="shrink-0">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={`/api/jobs/${j.id}/artifacts/${name}`} alt="Annotated frame" loading="lazy"
                        className="h-28 rounded-lg border border-[var(--border-color)] object-cover" />
                    </a>
                  );
                })}
              </div>
            </div>
          )}
          {isAdmin && (
            <div className="flex flex-wrap gap-2">
              {(j.status === "queued" || j.status === "running") && !j.cancel_requested && (
                <Button variant="danger" onClick={() => void act(`/api/jobs/${j.id}/cancel`)}>Cancel</Button>
              )}
              {(j.status === "failed" || j.status === "cancelled") && (
                <Button onClick={() => void act(`/api/jobs/${j.id}/retry`)}>Retry</Button>
              )}
              {j.status === "completed" && !r?.superseded_by && (
                <Button onClick={() => void act("/api/jobs", { video_id: j.video_id })}>Re-process with current zones</Button>
              )}
              {j.error_code === "DUPLICATE_VIDEO" && (
                <Button onClick={() => void act("/api/jobs", { video_id: j.video_id, allow_duplicate: true })}>Process anyway</Button>
              )}
            </div>
          )}
          {err !== null && <ErrorState error={err} />}
        </div>
      )}
    </li>
  );
}

function Info({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <dt className="text-[var(--text-muted)]">{k}</dt>
      <dd className="tabular-nums text-[var(--text-secondary)]">{v}</dd>
    </div>
  );
}
