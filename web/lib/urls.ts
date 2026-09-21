export function parseStartSeconds(value: string | string[] | null | undefined): number {
  const raw = Array.isArray(value) ? value[0] : value;
  if (!raw) {
    return 0;
  }
  const seconds = Number.parseFloat(raw);
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return 0;
  }
  return Math.round(seconds * 1000) / 1000;
}

export function deepLinkPath(deepLink: string): string | null {
  try {
    const url = new URL(deepLink);
    return `${url.pathname}${url.search}`;
  } catch {
    return null;
  }
}

export function searchPath(query: string): string {
  const trimmed = query.trim();
  return trimmed ? `/?q=${encodeURIComponent(trimmed)}` : "/";
}
