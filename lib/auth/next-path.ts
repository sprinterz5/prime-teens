/** `?next=` after login: only same-site absolute paths, never `//host` or a full URL. */
export function safeNextPath(raw: string | string[] | undefined | null): string | null {
  const value = Array.isArray(raw) ? raw[0] : raw;
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return null;
  if (value.startsWith("/login")) return null;
  return value;
}

export function loginPath(next: string): string {
  return `/login?next=${encodeURIComponent(next)}`;
}
