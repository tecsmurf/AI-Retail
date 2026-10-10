/** Response shapes of the PurpleSol API (see backend/app/api). */

export type Role = "admin" | "viewer";

export interface User {
  id: string;
  email: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface Store {
  id: string;
  store_code: string;
  name: string;
  address: string | null;
  city: string | null;
  timezone: string;
  pos_store_code: string | null;
  is_active: boolean;
  camera_count: number;
  zone_count: number;
  created_at: string;
}

export type CameraType = "entrance" | "zone" | "billing" | "other";
export type Point = [number, number];

export interface EntryLine {
  p1: Point;
  p2: Point;
  inside: "left" | "right";
}

export interface Camera {
  id: string;
  store_id: string;
  camera_code: string;
  name: string;
  camera_type: CameraType;
  is_active: boolean;
  resolution_width: number | null;
  resolution_height: number | null;
  fps: number | null;
  entry_line: EntryLine | null;
  has_reference_frame: boolean;
  reference_frame_width: number | null;
  reference_frame_height: number | null;
  config_version: number;
}

export const ZONE_TYPES = ["ENTRANCE", "SHELF", "DISPLAY", "QUEUE", "BILLING", "EXIT", "OTHER"] as const;
export type ZoneType = (typeof ZONE_TYPES)[number];

export interface Zone {
  id: string;
  zone_code: string;
  name: string;
  zone_type: ZoneType;
  is_revenue_zone: boolean;
  polygon: Point[] | null;
  camera_id: string | null;
  priority: number;
  color: string | null;
  display_order: number;
}

export interface CameraConfig {
  camera: Camera;
  zones: Zone[];
}

export interface Range {
  start: string;
  end: string;
  timezone: string;
  start_utc: string;
  end_utc: string;
}

export interface Envelope {
  store_id: string;
  range: Range;
  data: string[];
}

export interface Footfall {
  entries: number;
  exits: number;
  net_in_store_change: number;
  avg_daily_entries: number;
  peak_hour: string | null;
  peak_hour_entries: number;
  hourly: { hour: number; label: string; entries: number }[];
  daily: { date: string; entries: number; exits: number }[];
}

export interface ZoneMetric {
  zone_name: string;
  zone_type: string | null;
  visits: number;
  unique_tracks: number;
  avg_dwell_seconds: number | null;
  median_dwell_seconds: number | null;
  p90_dwell_seconds: number | null;
  max_dwell_seconds: number | null;
  total_dwell_seconds: number;
  hourly_visits: number[];
  cameras: string[];
  rank: number;
}

export interface QueueMetric {
  queue_visits: number;
  avg_wait_seconds: number | null;
  median_wait_seconds: number | null;
  p90_wait_seconds: number | null;
  max_wait_seconds: number | null;
  completed: number;
  abandoned: number;
  outcome_unknown: number;
  abandonment_rate: number | null;
  avg_queue_length: number | null;
  max_queue_length: number | null;
  current_queue_length: number | null;
  last_sample_at: string | null;
  throughput_per_hour: number | null;
  observed_queue_hours: number;
  hourly: { hour: number; label: string; avg_wait_seconds: number | null; avg_queue_length: number | null }[];
}

export interface Revenue {
  available: boolean;
  reason?: string;
  total_revenue: number | null;
  transactions: number | null;
  items: number | null;
  avg_order_value: number | null;
  top_brands: { brand: string; revenue: number; items: number }[];
  hourly: { hour: number; label: string; revenue: number }[];
}

export interface Conversion {
  entries: number;
  transactions: number | null;
  conversion_rate: number | null;
  revenue_per_entry: number | null;
  basis: string;
  notes: string[];
}

export interface Coverage {
  cameras: Record<string, { camera_type: string; videos: number; seconds: number }>;
  has_entrance_footage: boolean;
  has_queue_footage: boolean;
  processed_video_seconds: number;
}

export interface Overview extends Envelope {
  footfall: Footfall;
  zones: ZoneMetric[];
  queue: QueueMetric;
  revenue: Revenue;
  conversion: Conversion;
  avg_zone_dwell_seconds: number | null;
  zone_visits: number;
  coverage: Coverage;
  source_breakdown: Record<string, number>;
  active_alerts: number;
}

export interface DataExtent {
  store_id: string;
  timezone: string;
  sources: Record<string, { first_local_date: string | null; last_local_date: string | null; events?: number; transactions?: number }>;
}

export interface JourneyStep {
  sequence: number;
  event_type: string;
  zone_name: string | null;
  timestamp: string;
  dwell_seconds: number | null;
}

export interface Journey {
  id: string;
  customer_id: string;
  camera_id: string | null;
  job_id: string | null;
  source: string;
  entry_time: string;
  exit_time: string | null;
  duration_seconds: number | null;
  zones_visited: string[];
  zone_count: number;
  total_dwell_seconds: number | null;
  visited_billing: boolean;
  made_purchase: boolean;
  observed_entry: boolean;
  observed_exit: boolean;
  journey_type: string;
  steps: JourneyStep[];
}

export interface JourneyPage extends Envelope {
  total: number;
  limit: number;
  offset: number;
  items: Journey[];
}

export interface JourneyAnalytics extends Envelope {
  total_journeys: number;
  by_type: Record<string, number>;
  with_observed_entry: number;
  with_observed_exit: number;
  avg_duration_seconds: number | null;
  avg_zones_visited: number | null;
  top_paths: { path: string[]; count: number; avg_duration_seconds: number | null }[];
  scope_note: string;
}

export interface Insight {
  id: string;
  category: string;
  title: string;
  detail: string;
  evidence: Record<string, number | string | null>;
  confidence: "low" | "medium" | "high";
}

export interface Insights extends Envelope {
  insights: Insight[];
  insufficient_data: string[];
  journeys_considered: number;
  method: string;
}

export interface Anomaly {
  id: string;
  anomaly_type: string;
  severity: string;
  zone_name: string | null;
  description: string;
  metric_value: number | null;
  threshold_value: number | null;
  detected_at: string;
  is_resolved: boolean;
  resolved_at: string | null;
}

export interface Alert {
  id: string;
  alert_type: string;
  title: string;
  message: string;
  severity: string;
  is_read: boolean;
  created_at: string;
  anomaly_id: string | null;
}

export interface PosOrder {
  order_id: number;
  ordered_at: string;
  amount: number;
  items: number;
}

export interface CounterVisit {
  track: string;
  camera: string | null;
  start: string;
  end: string;
  dwell_seconds: number | null;
}

export interface PosCorrelation extends Envelope {
  method: string;
  parameters: { min_counter_dwell_seconds: number; grace_seconds: number };
  pos_configured: boolean;
  orders: number;
  counter_visits: number;
  matched: { order: PosOrder; visit: CounterVisit }[];
  unmatched_orders: PosOrder[];
  unmatched_counter_visits: CounterVisit[];
}

export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface Video {
  id: string;
  store_id: string;
  camera_id: string;
  original_filename: string;
  content_type: string | null;
  size_bytes: number | null;
  status: string;
  recorded_start: string | null;
  recorded_start_assumed: boolean;
  probe: Record<string, unknown> | null;
  created_at: string;
  uploaded_at: string | null;
}

export interface VideoCreated {
  video: Video;
  upload: { method: string; url: string; headers: Record<string, string>; direct_to_storage: boolean };
}

export interface JobResults {
  events?: Record<string, number>;
  event_total?: number;
  tracks_created?: number;
  tracks_discarded_short?: number;
  frames_analyzed?: number;
  decoded_seconds?: number;
  processing_seconds?: number;
  realtime_factor?: number | null;
  peak_rss_mb?: number;
  device?: string;
  max_people_in_frame?: number;
  warnings?: string[];
  journeys?: number;
  recorded_start_assumed?: boolean;
  superseded_by?: string;
  video?: { width: number; height: number; fps: number; duration_s: number | null; codec: string | null };
}

export interface Job {
  id: string;
  store_id: string;
  camera_id: string;
  video_id: string;
  status: JobStatus;
  cancel_requested: boolean;
  progress: number;
  stage: string | null;
  attempts: number;
  max_attempts: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  heartbeat_at: string | null;
  error_code: string | null;
  error_message: string | null;
  error_retryable: boolean | null;
  config: Record<string, unknown> | null;
  model_name: string | null;
  model_sha256: string | null;
  pipeline_version: string | null;
  results: JobResults | null;
  artifacts: { snapshots?: string[]; tracks?: string } | null;
  video_filename: string | null;
  camera_code: string | null;
}

export interface JobPage {
  total: number;
  items: Job[];
}

export interface SystemStatus {
  api: { version: string; env: string; uptime_seconds: number };
  workers: {
    worker_id: string;
    hostname: string | null;
    online: boolean;
    last_seen_at: string;
    last_seen_seconds_ago: number;
    current_job_id: string | null;
    model_loaded: boolean;
    model_error: string | null;
    device: string | null;
  }[];
  queue: {
    by_status: Record<string, number>;
    queue_depth: number;
    running: number;
    oldest_queued_age_seconds: number | null;
    finished_last_24h: Record<string, number>;
  };
  config: Record<string, string | number>;
}

export interface Readiness {
  status: "ready" | "not_ready";
  version: string;
  checks: Record<string, { ok: boolean; error?: string; [k: string]: unknown }>;
}
