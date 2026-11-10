// Security headers of the frontend. Pure: `next.config.ts` calls it, nothing here reads the environment.
// HSTS is not set here on purpose: Railway's edge already sends it.

export type SecurityHeader = { key: string; value: string };

/**
 * What the pages really load (checked in app/ and lib/): scripts and styles that Next.js emits itself
 * (inline RSC payload and `style` attributes included), the Nunito font that `next/font/google` downloads at
 * build time and serves from our own origin, same-origin images (supplier documents), the voice recorder's
 * `blob:` audio, and fetches to our own origin only (the browser never calls the API: `lib/api.ts` is
 * server-only and `API_URL` is read by the server).
 *
 * Decision: production keeps `script-src 'self' 'unsafe-inline'`. A strict policy needs a nonce per request,
 * which means dynamic rendering for every page and gives up the static shells of `cacheComponents` /
 * `partialPrefetching`; a policy that breaks the app is worse than one that is safe but compatible. What could be
 * hardened later: nonce-based `script-src` through `proxy.ts` (and drop `'unsafe-inline'` for scripts), or hashes
 * with Next's experimental SRI; and drop `'unsafe-inline'` from `style-src` once no component uses `style=`.
 * `'unsafe-eval'` and websockets are only for `next dev` (React's debugging stack and HMR).
 */
export function contentSecurityPolicy({ dev }: { dev: boolean }): string {
  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    "script-src": [
      "'self'",
      "'unsafe-inline'",
      ...(dev ? ["'unsafe-eval'"] : []),
    ],
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "data:", "blob:"],
    "font-src": ["'self'", "data:"],
    "media-src": ["'self'", "blob:"],
    "connect-src": ["'self'", ...(dev ? ["ws:", "wss:"] : [])],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
  };
  return Object.entries(directives)
    .map(([name, sources]) => `${name} ${sources.join(" ")}`)
    .join("; ");
}

// The voice dictation (lib/voz.ts, lib/use-recorder.ts) needs the microphone, only for our own origin.
export const PERMISSIONS_POLICY = [
  "microphone=(self)",
  "camera=()",
  "geolocation=()",
  "payment=()",
  "usb=()",
  "serial=()",
  "midi=()",
  "accelerometer=()",
  "gyroscope=()",
  "magnetometer=()",
].join(", ");

export function securityHeaders({ dev }: { dev: boolean }): SecurityHeader[] {
  return [
    { key: "Content-Security-Policy", value: contentSecurityPolicy({ dev }) },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "Permissions-Policy", value: PERMISSIONS_POLICY },
  ];
}
