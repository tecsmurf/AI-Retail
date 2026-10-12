/**
 * PurpleSol API client.
 *
 * The browser only talks to its own origin: Next.js rewrites /api/* to the
 * backend (API_ORIGIN, see next.config.ts), so the session cookie is
 * first-party and httpOnly. Every state-changing request carries the CSRF
 * header the backend requires for cookie-authenticated writes.
 */

export const CSRF_HEADER = "X-PurpleSol-CSRF";

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
  }
}

type Query = Record<string, string | number | boolean | null | undefined>;

function withQuery(path: string, query?: Query): string {
  if (!query) return path;
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

function detailMessage(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d))
      return d
        .map((e) => (e && typeof e === "object" && "msg" in e ? String((e as { msg: unknown }).msg) : String(e)))
        .join("; ");
  }
  if (status === 0) return "Cannot reach the PurpleSol API";
  return `Request failed (${status})`;
}

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

export async function api<T>(
  path: string,
  opts: { method?: string; query?: Query; json?: unknown; body?: BodyInit; signal?: AbortSignal } = {},
): Promise<T> {
  const method = opts.method ?? (opts.json !== undefined || opts.body ? "POST" : "GET");
  const headers: Record<string, string> = {};
  if (method !== "GET") headers[CSRF_HEADER] = "1";
  if (opts.json !== undefined) headers["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(withQuery(path, opts.query), {
      method,
      headers,
      body: opts.json !== undefined ? JSON.stringify(opts.json) : opts.body,
      credentials: "same-origin",
      signal: opts.signal,
      cache: "no-store",
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "Cannot reach the PurpleSol API. Check your connection.");
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let body: unknown = undefined;
  try {
    body = text ? JSON.parse(text) : undefined;
  } catch {
    body = text;
  }
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith("/api/auth/login")) onUnauthorized?.();
    throw new ApiError(res.status, detailMessage(body, res.status), body);
  }
  return body as T;
}

/**
 * Upload a file with progress. For S3/R2 the URL is a presigned PUT straight
 * to the bucket (no cookies, no CSRF header); for local storage it is the
 * API's own upload endpoint.
 */
export function uploadFile(
  url: string,
  file: File,
  headers: Record<string, string>,
  direct: boolean,
  onProgress: (fraction: number) => void,
): { promise: Promise<void>; abort: () => void } {
  const xhr = new XMLHttpRequest();
  const promise = new Promise<void>((resolve, reject) => {
    xhr.open("PUT", url);
    for (const [k, v] of Object.entries(headers)) xhr.setRequestHeader(k, v);
    if (!direct) {
      xhr.withCredentials = true;
      xhr.setRequestHeader(CSRF_HEADER, "1");
    }
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else {
        let msg = `Upload failed (${xhr.status})`;
        try {
          msg = detailMessage(JSON.parse(xhr.responseText), xhr.status);
        } catch {
          /* not JSON (e.g. S3 XML) */
        }
        reject(new ApiError(xhr.status, msg));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, "Upload interrupted. Check your connection and try again."));
    xhr.onabort = () => reject(new ApiError(0, "Upload cancelled"));
    xhr.send(file);
  });
  return { promise, abort: () => xhr.abort() };
}
