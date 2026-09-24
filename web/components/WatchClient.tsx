"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import Player from "@/components/Player";
import { PlayerMessage } from "@/components/ResultStates";
import { errorMessage, getAsset } from "@/lib/api";
import { formatClock, formatTimestamp } from "@/lib/format";
import type { Asset } from "@/lib/types";

type AssetLoad =
  | { status: "loading" }
  | { status: "ready"; asset: Asset }
  | { status: "error"; message: string };

export default function WatchClient({
  assetId,
  startSeconds,
}: {
  assetId: string;
  startSeconds: number;
}) {
  const abortRef = useRef<AbortController | null>(null);
  const [load, setLoad] = useState<AssetLoad>({ status: "loading" });
  const [mediaError, setMediaError] = useState(false);
  const [playerKey, setPlayerKey] = useState(0);

  const loadAsset = useCallback((id: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    getAsset(id, { signal: controller.signal })
      .then((asset) => setLoad({ status: "ready", asset }))
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setLoad({ status: "error", message: errorMessage(cause) });
        }
      });
  }, []);

  useEffect(() => {
    loadAsset(assetId);
    return () => abortRef.current?.abort();
  }, [assetId, loadAsset]);

  function retryAsset() {
    setLoad({ status: "loading" });
    loadAsset(assetId);
  }

  function retryMedia() {
    setMediaError(false);
    setPlayerKey((value) => value + 1);
  }

  if (load.status === "error") {
    return (
      <div className="mt-6">
        <PlayerMessage
          title="This moment could not be opened"
          message={load.message}
          onRetry={retryAsset}
        />
      </div>
    );
  }

  if (load.status === "loading") {
    return (
      <div className="mt-6" aria-busy="true">
        <div className="h-6 w-56 animate-pulse bg-paper-deep" />
        <div className="mt-4 aspect-video w-full animate-pulse border border-rule bg-paper-deep" />
      </div>
    );
  }

  const asset = load.asset;

  return (
    <div className="mt-6">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h1 className="font-display text-2xl font-semibold tracking-tight">{asset.filename}</h1>
        <p className="font-code text-xs tabular-nums text-ink-soft">
          {formatClock(asset.duration_s)} · {asset.fps.toFixed(2)} fps · {asset.codec.toUpperCase()}
        </p>
      </div>
      {startSeconds > 0 ? (
        <p className="mt-1 text-xs text-ink-soft">
          Opens at{" "}
          <span className="font-code tabular-nums text-ink">
            {formatTimestamp(startSeconds)}
          </span>
        </p>
      ) : null}
      <div className="mt-4">
        {mediaError ? (
          <PlayerMessage
            title="Playback unavailable"
            message="The playback proxy for this asset could not be loaded."
            onRetry={retryMedia}
          />
        ) : (
          <Player
            key={playerKey}
            src={asset.proxy_url}
            startSeconds={startSeconds}
            onMediaError={() => setMediaError(true)}
          />
        )}
      </div>
    </div>
  );
}
