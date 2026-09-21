"use client";

import { useEffect, useMemo, useState } from "react";

import { getAsset } from "@/lib/api";

const cache = new Map<string, string>();

export function useAssetNames(assetIds: string[]): Record<string, string> {
  const key = JSON.stringify(Array.from(new Set(assetIds)).sort());
  const ids = useMemo(() => JSON.parse(key) as string[], [key]);
  const [, setRevision] = useState(0);

  useEffect(() => {
    const missing = ids.filter((id) => !cache.has(id));
    if (missing.length === 0) {
      return;
    }
    const controller = new AbortController();
    Promise.all(
      missing.map((id) =>
        getAsset(id, { signal: controller.signal })
          .then((asset) => cache.set(id, asset.filename))
          .catch(() => undefined),
      ),
    ).then(() => {
      if (!controller.signal.aborted) {
        setRevision((value) => value + 1);
      }
    });
    return () => controller.abort();
  }, [ids]);

  return cachedNames(ids);
}

function cachedNames(ids: string[]): Record<string, string> {
  const names: Record<string, string> = {};
  for (const id of ids) {
    const name = cache.get(id);
    if (name) {
      names[id] = name;
    }
  }
  return names;
}
