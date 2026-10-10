import type { NextConfig } from "next";

/**
 * The browser calls /api/* on this origin and Next.js forwards it to the
 * FastAPI backend, so the session cookie stays first-party.
 * API_ORIGIN is read at build time (e.g. https://purplesol-api.up.railway.app).
 */
const apiOrigin = (process.env.API_ORIGIN ?? "http://localhost:8000").replace(/\/+$/, "");

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${apiOrigin}/api/:path*` },
      { source: "/health/:path*", destination: `${apiOrigin}/health/:path*` },
    ];
  },
  async redirects() {
    return [
      { source: "/live", destination: "/videos", permanent: false },
      { source: "/heatmap", destination: "/analytics", permanent: false },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
