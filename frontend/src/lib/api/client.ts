import { env } from '../env';
import { getFirebaseAuth, refreshIdToken } from '../firebase';
import { useAuthStore } from '@/stores/authStore';

export interface FetchOptions extends RequestInit {
  json?: unknown;
  query?: Record<string, string | number | boolean | undefined>;
  raw?: boolean;
}

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
  }
}

/** Raw auth token (no "Bearer " prefix) — used for the WebSocket `?token=` query param. */
export async function getAuthToken(): Promise<string | null> {
  return getToken();
}

async function getToken(): Promise<string | null> {
  const stored = useAuthStore.getState();
  // Demo session: token + uid live entirely in our store; never consult Firebase (which may
  // still be in the process of signing out a prior anonymous user, racing the request).
  if (stored.uid?.startsWith('demo-')) {
    return stored.idToken;
  }
  const auth = getFirebaseAuth();
  if (auth?.currentUser) {
    return auth.currentUser.getIdToken();
  }
  return stored.idToken;
}

function buildUrl(path: string, query?: FetchOptions['query']): string {
  const base = env.apiBase || '';
  const url = new URL(path.startsWith('http') ? path : `${base}${path}`, window.location.origin);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

export async function api<T = unknown>(path: string, opts: FetchOptions = {}): Promise<T> {
  const headers = new Headers(opts.headers ?? {});
  if (opts.json !== undefined) {
    headers.set('Content-Type', 'application/json');
  }
  let token = await getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const url = buildUrl(path, opts.query);
  const init: RequestInit = {
    ...opts,
    headers,
    body: opts.json !== undefined ? JSON.stringify(opts.json) : opts.body,
  };

  let resp = await fetch(url, init);
  if (resp.status === 401 && token) {
    token = await refreshIdToken();
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
      resp = await fetch(url, { ...init, headers });
    }
  }
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(resp.status, detail);
  }
  if (opts.raw) return resp as unknown as T;
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}
