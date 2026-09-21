const DEFAULT_API_URL = "http://localhost:8000";

export function apiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL).replace(/\/+$/, "");
}
