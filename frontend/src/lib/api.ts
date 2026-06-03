/** PurpleSol API client */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API Error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// ── Store APIs ────────────────────────────────────────────────────
export const api = {
  // Stores
  getStores: () => fetchAPI<any[]>("/api/stores"),
  getStore: (id: string) => fetchAPI<any>(`/api/stores/${id}`),
  getStoreCameras: (id: string) => fetchAPI<any[]>(`/api/stores/${id}/cameras`),
  getStoreZones: (id: string) => fetchAPI<any[]>(`/api/stores/${id}/zones`),

  // Analytics
  getAnalytics: (storeId: string) => fetchAPI<any>(`/api/analytics/${storeId}`),
  getFootfall: (storeId: string) => fetchAPI<any>(`/api/analytics/${storeId}/footfall`),
  getZoneAnalytics: (storeId: string) => fetchAPI<any>(`/api/analytics/${storeId}/zones`),
  getConversion: (storeId: string) => fetchAPI<any>(`/api/analytics/${storeId}/conversion`),
  getQueue: (storeId: string) => fetchAPI<any>(`/api/analytics/${storeId}/queue`),
  getDemographics: (storeId: string) => fetchAPI<any>(`/api/analytics/${storeId}/demographics`),
  getRevenue: (storeId: string) => fetchAPI<any>(`/api/analytics/${storeId}/revenue`),

  // Journeys
  getJourneys: (storeId: string) => fetchAPI<any>(`/api/analytics/${storeId}/journeys`),
  getJourneyAnalytics: (storeId: string) => fetchAPI<any>(`/api/analytics/${storeId}/journeys/analytics`),
  getTopPaths: (storeId: string) => fetchAPI<any[]>(`/api/analytics/${storeId}/journeys/top-paths`),

  // Anomalies
  getAnomalies: (storeId: string) => fetchAPI<any[]>(`/api/analytics/${storeId}/anomalies`),
  getAlerts: (storeId: string) => fetchAPI<any[]>(`/api/analytics/${storeId}/alerts`),

  // Events
  getEvents: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return fetchAPI<any[]>(`/api/events${qs}`);
  },
};

// ── WebSocket ─────────────────────────────────────────────────────
export function connectWebSocket(storeId?: string): WebSocket {
  const wsBase = API_BASE.replace("http", "ws");
  const path = storeId ? `/ws/store/${storeId}` : "/ws";
  return new WebSocket(`${wsBase}${path}`);
}
