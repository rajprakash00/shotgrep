import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, errorMessage, getAsset, searchMoments } from "@/lib/api";
import { jsonResponse } from "@/test-helpers";

const PAYLOAD = {
  query: "robotics",
  model: { name: "siglip", precision: "int8", revision: "abc" },
  results: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("searchMoments", () => {
  it("queries the search endpoint with the query and k", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(PAYLOAD));
    vi.stubGlobal("fetch", fetchMock);

    await expect(searchMoments("robotics space", { k: 5 })).resolves.toEqual(PAYLOAD);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("http://api.test/search?q=robotics+space&k=5");
  });

  it("reports the API detail on a failed search", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "no index" }, 503)));

    const failure = searchMoments("anything", { k: 5 }).catch((error: unknown) => error);
    await expect(failure).resolves.toBeInstanceOf(ApiError);
    const error = (await failure) as ApiError;
    expect(error.message).toBe("no index");
    expect(error.status).toBe(503);
  });

  it("reports an unreachable API", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));

    await expect(searchMoments("anything", { k: 5 })).rejects.toThrow(/can't reach/i);
  });
});

describe("getAsset", () => {
  it("queries the asset endpoint", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test/");
    const asset = { asset_id: "abc", filename: "clip.mp4", proxy_url: "http://api.test/media/abc/proxy.mp4" };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(asset));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getAsset("abc")).resolves.toEqual(asset);
    expect(fetchMock.mock.calls[0][0]).toBe("http://api.test/assets/abc");
  });

  it("falls back to a status message when the error body is not JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("boom", { status: 500 })));

    await expect(getAsset("abc")).rejects.toThrow("The API answered with status 500.");
  });
});

describe("errorMessage", () => {
  it("prefers the error message", () => {
    expect(errorMessage(new ApiError("no index", 503))).toBe("no index");
    expect(errorMessage("nope")).toBe("Something went wrong.");
  });
});
