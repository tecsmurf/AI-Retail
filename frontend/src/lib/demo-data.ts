/** Demo/mock data + real CV pipeline results for dashboard display */

export const DEMO_STORES = [
  {
    id: "store-1",
    store_code: "store_1076",
    name: "Purplle Beauty — Mumbai Store 1",
    city: "Mumbai",
    camera_count: 4,
    zone_count: 15,
    is_active: true,
  },
  {
    id: "store-2",
    store_code: "store_1077",
    name: "Purplle Beauty — Mumbai Store 2",
    city: "Mumbai",
    camera_count: 4,
    zone_count: 7,
    is_active: true,
  },
];

export const DEMO_OVERVIEW = {
  visitors_today: 247,
  active_visitors: 12,
  conversion_rate: 23.4,
  avg_dwell_time: 142,
  revenue_today: 48750,
  peak_hour: "6 PM",
  active_alerts: 3,
};

export const DEMO_HOURLY = Array.from({ length: 24 }, (_, i) => {
  const labels = [
    "12 AM","1 AM","2 AM","3 AM","4 AM","5 AM","6 AM","7 AM","8 AM","9 AM","10 AM","11 AM",
    "12 PM","1 PM","2 PM","3 PM","4 PM","5 PM","6 PM","7 PM","8 PM","9 PM","10 PM","11 PM",
  ];
  const base = i >= 9 && i <= 21 ? Math.floor(Math.random() * 30 + 10) : Math.floor(Math.random() * 5);
  return { hour: i, visitors: base, label: labels[i] };
});

export const DEMO_ZONES = [
  { zone_name: "Faces Canada", zone_type: "SHELF", total_visits: 89, unique_visitors: 67, avg_dwell_seconds: 95.2, popularity_rank: 1 },
  { zone_name: "L'Oreal", zone_type: "SHELF", total_visits: 76, unique_visitors: 58, avg_dwell_seconds: 112.8, popularity_rank: 2 },
  { zone_name: "Minimalist", zone_type: "SHELF", total_visits: 72, unique_visitors: 55, avg_dwell_seconds: 88.4, popularity_rank: 3 },
  { zone_name: "Foxtale", zone_type: "SHELF", total_visits: 65, unique_visitors: 48, avg_dwell_seconds: 76.1, popularity_rank: 4 },
  { zone_name: "Mars + NY Bae", zone_type: "SHELF", total_visits: 58, unique_visitors: 42, avg_dwell_seconds: 67.3, popularity_rank: 5 },
  { zone_name: "Aqualogica", zone_type: "SHELF", total_visits: 52, unique_visitors: 39, avg_dwell_seconds: 82.7, popularity_rank: 6 },
  { zone_name: "Makeup Unit", zone_type: "DISPLAY", total_visits: 48, unique_visitors: 35, avg_dwell_seconds: 145.6, popularity_rank: 7 },
  { zone_name: "Beauty", zone_type: "SHELF", total_visits: 44, unique_visitors: 31, avg_dwell_seconds: 58.9, popularity_rank: 8 },
  { zone_name: "Men's Section", zone_type: "SHELF", total_visits: 28, unique_visitors: 22, avg_dwell_seconds: 43.2, popularity_rank: 9 },
  { zone_name: "TFS", zone_type: "SHELF", total_visits: 25, unique_visitors: 19, avg_dwell_seconds: 51.8, popularity_rank: 10 },
];

export const DEMO_CONVERSION = {
  total_visitors: 247,
  zone_visitors: 198,
  product_interactions: 124,
  billing_visitors: 72,
  purchases: 58,
  overall_conversion_rate: 23.4,
  revenue_per_visitor: 197.4,
  avg_basket_value: 840.5,
};

export const DEMO_QUEUE = {
  avg_wait_seconds: 28.5,
  max_wait_seconds: 95,
  current_queue_length: 3,
  abandonment_rate: 8.2,
  total_served: 58,
  total_abandoned: 5,
};

export const DEMO_TOP_PATHS = [
  { path: ["ENTRY", "Faces Canada", "L'Oreal", "Billing", "EXIT"], count: 18, avg_duration_seconds: 480, conversion_rate: 100 },
  { path: ["ENTRY", "Minimalist", "Foxtale", "EXIT"], count: 15, avg_duration_seconds: 320, conversion_rate: 0 },
  { path: ["ENTRY", "L'Oreal", "Makeup Unit", "Billing", "EXIT"], count: 12, avg_duration_seconds: 540, conversion_rate: 100 },
  { path: ["ENTRY", "Mars + NY Bae", "EXIT"], count: 11, avg_duration_seconds: 180, conversion_rate: 0 },
  { path: ["ENTRY", "Aqualogica", "Minimalist", "Faces Canada", "Billing", "EXIT"], count: 9, avg_duration_seconds: 720, conversion_rate: 100 },
];

export const DEMO_JOURNEY_ANALYTICS = {
  total_journeys: 247,
  avg_journey_duration: 342,
  avg_zones_visited: 2.8,
  conversion_journeys: 58,
  browse_journeys: 142,
  bounce_journeys: 47,
  conversion_rate: 23.4,
};

export const DEMO_ALERTS = [
  { id: "a1", alert_type: "LONG_QUEUE", title: "Long Queue at Billing", message: "Average wait time exceeded 45s for 5 customers", severity: "high", created_at: new Date().toISOString(), is_read: false },
  { id: "a2", alert_type: "ABNORMAL_DWELL", title: "Extended Dwell in Makeup Unit", message: "Customer spent 8 minutes in Makeup Unit zone", severity: "medium", created_at: new Date(Date.now() - 900000).toISOString(), is_read: false },
  { id: "a3", alert_type: "TRAFFIC_DROP", title: "Traffic Drop Detected", message: "Visitor traffic dropped 60% compared to previous hour", severity: "medium", created_at: new Date(Date.now() - 1800000).toISOString(), is_read: true },
];

export const DEMO_DEMOGRAPHICS = {
  gender: { F: 156, M: 91 },
  age_buckets: { "18-24": 68, "25-34": 102, "35-44": 52, "45-54": 25 },
};

export const DEMO_REVENUE = {
  total_revenue: 48750,
  total_orders: 58,
  total_items: 142,
  avg_order_value: 840.5,
  top_brands: [
    { brand: "Faces Canada", revenue: 14520, items_sold: 38 },
    { brand: "L'Oreal", revenue: 8340, items_sold: 15 },
    { brand: "Minimalist", revenue: 6280, items_sold: 22 },
    { brand: "NY Bae", revenue: 4890, items_sold: 18 },
    { brand: "Good Vibes", revenue: 3420, items_sold: 28 },
  ],
};

// ── Real CV Pipeline Results (from actual CCTV processing) ──────
export const CV_PIPELINE_RESULTS = {
  processed_at: "2026-06-03T10:28:00+05:30",
  total_videos: 8,
  total_events: 494,
  processing_time_seconds: 195,
  model: "YOLO11n",
  tracker: "ByteTrack",

  stores: {
    store_1076: {
      name: "Mumbai Store 1",
      total_events: 183,
      entries: 42,
      exits: 42,
      zone_enters: 22,
      zone_exits: 40,
      billing_completed: 19,
      conversion_rate: 45.2,
      unique_tracks: 71,
      cameras_processed: 4,
      zones_detected: [
        { name: "Entrance", visits: 12, avg_dwell: 4.4 },
        { name: "Mars + NY Bae", visits: 7, avg_dwell: 2.3 },
        { name: "Men's Section", visits: 2, avg_dwell: 0.5 },
        { name: "L'Oreal", visits: 1, avg_dwell: 0.5 },
      ],
      queue: { served: 19, avg_wait: 6.6, max_wait: 52.8, min_wait: 0.6 },
    },
    store_1077: {
      name: "Mumbai Store 2",
      total_events: 311,
      entries: 68,
      exits: 66,
      zone_enters: 36,
      zone_exits: 65,
      billing_completed: 47,
      conversion_rate: 69.1,
      unique_tracks: 117,
      cameras_processed: 4,
      zones_detected: [
        { name: "Entrance", visits: 36, avg_dwell: 1.2 },
      ],
      queue: { served: 47, avg_wait: 4.1, max_wait: 27.6, min_wait: 0.6 },
    },
  },

  event_breakdown: {
    ENTRY: 110,
    EXIT: 108,
    ZONE_EXIT: 105,
    QUEUE_COMPLETED: 66,
    ZONE_ENTER: 58,
    QUEUE_ENTER: 47,
  },
};
