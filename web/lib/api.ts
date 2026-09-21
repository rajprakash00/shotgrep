import { apiBaseUrl } from "@/lib/config";
import type { Asset, SearchPayload } from "@/lib/types";

export class ApiError extends Error {
  readonly status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "Something went wrong.";
}

async function getJson<T>(path: string, params: URLSearchParams, signal?: AbortSignal): Promise<T> {
  const query = params.size > 0 ? `?${params}` : "";
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}${query}`, {
      signal,
      headers: { accept: "application/json" },
    });
  } catch (error) {
    if (signal?.aborted) {
      throw error;
    }
    throw new ApiError("Can't reach the shotgrep API. Is it running?");
  }
  if (!response.ok) {
    throw new ApiError(await detailOf(response), response.status);
  }
  return (await response.json()) as T;
}

async function detailOf(response: Response): Promise<string> {
  const fallback = `The API answered with status ${response.status}.`;
  try {
    const body = (await response.json()) as { detail?: unknown };
    return typeof body.detail === "string" && body.detail ? body.detail : fallback;
  } catch {
    return fallback;
  }
}

export function searchMoments(
  query: string,
  options: { k: number; signal?: AbortSignal },
): Promise<SearchPayload> {
  const params = new URLSearchParams({ q: query, k: String(options.k) });
  return getJson<SearchPayload>("/search", params, options.signal);
}

export function getAsset(assetId: string, options: { signal?: AbortSignal } = {}): Promise<Asset> {
  return getJson<Asset>(`/assets/${encodeURIComponent(assetId)}`, new URLSearchParams(), options.signal);
}
