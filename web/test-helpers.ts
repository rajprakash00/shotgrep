import { vi } from "vitest";

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

export function stubFetch(routes: Record<string, () => Response>): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    for (const [path, respond] of Object.entries(routes)) {
      if (url.includes(path)) {
        return Promise.resolve(respond());
      }
    }
    return Promise.resolve(jsonResponse({ detail: "not found" }, 404));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
