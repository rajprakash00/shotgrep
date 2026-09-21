import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import WatchClient from "@/components/WatchClient";
import { jsonResponse } from "@/test-helpers";

const ASSET = {
  asset_id: "asset",
  filename: "Big Buck Bunny",
  duration_s: 596.46,
  fps: 24,
  codec: "h264",
  status: "indexed",
  proxy_url: "http://localhost:8000/media/asset/proxy.mp4",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("WatchClient", () => {
  it("opens the proxy at the requested moment", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(ASSET)));
    const { container } = render(<WatchClient assetId="asset" startSeconds={4.44} />);

    expect(await screen.findByText("Big Buck Bunny")).toBeInTheDocument();
    expect(screen.getByText(/Opens at/)).toBeInTheDocument();
    expect(screen.getByText("0:04.4")).toBeInTheDocument();

    const video = container.querySelector("video");
    expect(video).not.toBeNull();
    expect(video).toHaveAttribute("src", "http://localhost:8000/media/asset/proxy.mp4");
    expect(video).toHaveAttribute("preload", "metadata");
    expect((video as HTMLVideoElement).currentTime).toBe(4.44);
  });

  it("seeks again once metadata arrives", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(ASSET)));
    const { container } = render(<WatchClient assetId="asset" startSeconds={12.5} />);
    await screen.findByText("Big Buck Bunny");
    const video = container.querySelector("video");
    expect(video).not.toBeNull();

    (video as HTMLVideoElement).currentTime = 0;
    fireEvent.loadedMetadata(video as HTMLVideoElement);
    expect((video as HTMLVideoElement).currentTime).toBe(12.5);
  });

  it("starts at the beginning without a timestamp", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(ASSET)));
    const { container } = render(<WatchClient assetId="asset" startSeconds={0} />);

    await screen.findByText("Big Buck Bunny");
    expect(screen.queryByText(/Opens at/)).not.toBeInTheDocument();
    expect((container.querySelector("video") as HTMLVideoElement).currentTime).toBe(0);
  });

  it("reports a missing proxy and retries by remounting the player", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(ASSET)));
    const { container } = render(<WatchClient assetId="asset" startSeconds={0} />);

    await screen.findByText("Big Buck Bunny");
    const video = container.querySelector("video");
    expect(video).not.toBeNull();
    fireEvent.error(video as HTMLVideoElement);

    expect(await screen.findByText("Playback unavailable")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(container.querySelector("video")).not.toBeNull();
  });

  it("reports an asset that is not in the index", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "no asset 'nope' in the index" }, 404)),
    );
    render(<WatchClient assetId="nope" startSeconds={0} />);

    expect(await screen.findByText("This moment could not be opened")).toBeInTheDocument();
    expect(screen.getByText("no asset 'nope' in the index")).toBeInTheDocument();
  });

  it("retries after a failed asset lookup", async () => {
    let calls = 0;
    const fetchMock = vi.fn(() => {
      calls += 1;
      return Promise.resolve(
        calls === 1
          ? jsonResponse({ detail: "Can't reach the shotgrep API. Is it running?" }, 503)
          : jsonResponse(ASSET),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<WatchClient assetId="asset" startSeconds={0} />);

    await userEvent.click(await screen.findByRole("button", { name: "Try again" }));

    await waitFor(() => expect(screen.getByText("Big Buck Bunny")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
