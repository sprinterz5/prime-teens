/**
 * In-memory fixed-window counter of failed login codes: a 6-digit code is
 * guessable without one. Only failures count — a whole class logging in
 * from one school Wi-Fi (one public IP) must not lock itself out. The
 * platform runs as a single long-lived Node process
 * (deploy/systemd/primeteens-web.service), so process memory is enough; a
 * restart only resets the windows.
 */

type Window = { count: number; resetAt: number };

const windows = new Map<string, Window>();

function current(key: string): Window | undefined {
  const w = windows.get(key);
  return w && w.resetAt > Date.now() ? w : undefined;
}

export function isLimited(key: string, limit: number): boolean {
  return (current(key)?.count ?? 0) >= limit;
}

export function recordFailure(key: string, windowMs: number): void {
  const now = Date.now();
  if (windows.size > 10_000) {
    for (const [k, w] of windows) if (w.resetAt <= now) windows.delete(k);
  }
  const w = current(key);
  if (w) w.count += 1;
  else windows.set(key, { count: 1, resetAt: now + windowMs });
}

/** Client IP as nginx forwards it (deploy/nginx/primeteens.conf); "local" in dev. */
export function clientIp(request: Request): string {
  const real = request.headers.get("x-real-ip");
  if (real) return real.trim();
  const forwarded = request.headers.get("x-forwarded-for");
  if (forwarded) return forwarded.split(",")[0].trim();
  return "local";
}
