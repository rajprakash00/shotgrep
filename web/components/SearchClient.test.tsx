import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import SearchClient from "@/components/SearchClient";
import type { Moment, SearchPayload } from "@/lib/types";
import { jsonResponse, stubFetch } from "@/test-helpers";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

function moment(overrides: Partial<Moment> = {}): Moment {
  return {
    moment_id: "asset-frame-00002000",
    asset_id: "asset",
    kind: "shot_start",
    start_s: 2,
    end_s: 4,
    thumbnail_url: "http://localhost:8000/media/asset/thumbnails/00002000.jpg",
    snippet: null,
    score: 0.9,
    deep_link: "http://localhost:3000/watch/asset?t=2",
    ...overrides,
  };
}

function payload(results: Moment[]): SearchPayload {
  return {
    query: "a bridge",
    model: { name: "siglip", precision: "int8", revision: "abc" },
    results,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SearchClient", () => {
  it("shows examples before the first search", () => {
    stubFetch({});
    render(<SearchClient query="" />);

    expect(screen.getByText("Ask for a moment in plain language")).toBeInTheDocument();
    expect(screen.getByRole("searchbox")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
  });

  it("searches from an example", async () => {
    stubFetch({});
    render(<SearchClient query="" />);

    await userEvent.click(screen.getByRole("button", { name: "a rabbit sleeping inside a burrow" }));
    expect(push).toHaveBeenCalledWith("/?q=a%20rabbit%20sleeping%20inside%20a%20burrow");
  });

  it("renders results with thumbnails, timestamps, and deep links", async () => {
    stubFetch({
      "/search": () => jsonResponse(payload([moment({ snippet: "look at this" })])),
      "/assets/asset": () =>
        jsonResponse({ asset_id: "asset", filename: "Big Buck Bunny", duration_s: 596, proxy_url: "x" }),
    });
    render(<SearchClient query="a bridge" />);

    const card = await screen.findByRole("link");
    expect(card).toHaveAttribute("href", "/watch/asset?t=2");
    expect(card.querySelector("img")).toHaveAttribute(
      "src",
      "http://localhost:8000/media/asset/thumbnails/00002000.jpg",
    );
    expect(within(card).getByText("0:02.0")).toBeInTheDocument();
    expect(within(card).getByText("shot start")).toBeInTheDocument();
    expect(within(card).getByText("“look at this”")).toBeInTheDocument();
    expect(await within(card).findByText("Big Buck Bunny")).toBeInTheDocument();
  });

  it("searches for the query in the URL", async () => {
    const fetchMock = stubFetch({ "/search": () => jsonResponse(payload([moment()])) });
    render(<SearchClient query="robotics" />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(String(fetchMock.mock.calls[0][0])).toBe("http://localhost:8000/search?q=robotics&k=12");
  });

  it("reports an empty result set", async () => {
    stubFetch({ "/search": () => jsonResponse(payload([])) });
    render(<SearchClient query="a purple giraffe" />);

    expect(await screen.findByText("No moments matched “a purple giraffe”")).toBeInTheDocument();
  });

  it("reports a failed search and retries", async () => {
    let calls = 0;
    const fetchMock = stubFetch({
      "/search": () => {
        calls += 1;
        return calls === 1
          ? jsonResponse({ detail: "no index at work/index" }, 503)
          : jsonResponse(payload([moment()]));
      },
    });
    render(<SearchClient query="robotics" />);

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("no index at work/index")).toBeInTheDocument();
    await userEvent.click(within(alert).getByRole("button", { name: "Try again" }));

    expect(await screen.findByRole("link")).toHaveAttribute("href", "/watch/asset?t=2");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("loads more results with a larger k", async () => {
    const many = Array.from({ length: 12 }, (_, index) =>
      moment({ moment_id: `asset-frame-${index}`, start_s: index }),
    );
    const fetchMock = stubFetch({
      "/search": () => jsonResponse(payload(many)),
      "/assets/": () => jsonResponse({ asset_id: "asset", filename: "Big Buck Bunny" }),
    });
    render(<SearchClient query="a bridge" />);

    await screen.findByRole("button", { name: "Load more" });
    await userEvent.click(screen.getByRole("button", { name: "Load more" }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.some((call) => String(call[0]).endsWith("k=24"))).toBe(true),
    );
  });

  it("keeps the loaded results when loading more fails", async () => {
    const many = Array.from({ length: 12 }, (_, index) =>
      moment({ moment_id: `asset-frame-${index}`, start_s: index }),
    );
    let searches = 0;
    stubFetch({
      "/search": () => {
        searches += 1;
        return searches === 1
          ? jsonResponse(payload(many))
          : jsonResponse({ detail: "the index went away" }, 503);
      },
      "/assets/": () => jsonResponse({ asset_id: "asset", filename: "Big Buck Bunny" }),
    });
    render(<SearchClient query="a bridge" />);

    await userEvent.click(await screen.findByRole("button", { name: "Load more" }));

    expect(await screen.findByText("the index went away")).toBeInTheDocument();
    expect(screen.getAllByRole("link")).toHaveLength(12);
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
