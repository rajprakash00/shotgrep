"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { EmptyResults, ErrorState, IdleState, SkeletonGrid } from "@/components/ResultStates";
import ResultsGrid from "@/components/ResultsGrid";
import { errorMessage, searchMoments } from "@/lib/api";
import type { SearchPayload } from "@/lib/types";
import { useAssetNames } from "@/lib/use-asset-names";
import { searchPath } from "@/lib/urls";

const PAGE_SIZE = 12;
const MAX_K = 100;

export default function SearchClient({ query }: { query: string }) {
  const router = useRouter();
  const abortRef = useRef<AbortController | null>(null);
  const [input, setInput] = useState(query);
  const [page, setPage] = useState<{ query: string; limit: number } | null>(null);
  const [payload, setPayload] = useState<SearchPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(query));
  const limit = page?.query === query ? page.limit : PAGE_SIZE;

  const runSearch = useCallback((text: string, size: number) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    searchMoments(text, { k: size, signal: controller.signal })
      .then((next) => {
        setPayload(next);
        setError(null);
        setLoading(false);
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setError(errorMessage(cause));
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!query) {
      return;
    }
    runSearch(query, limit);
    return () => abortRef.current?.abort();
  }, [query, limit, runSearch]);

  const results = payload?.results ?? [];
  const assetNames = useAssetNames(results.map((moment) => moment.asset_id));

  function retry() {
    setLoading(true);
    runSearch(query, limit);
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = input.trim();
    if (next === query) {
      retry();
      return;
    }
    router.push(searchPath(next));
  }

  function searchExample(example: string) {
    setInput(example);
    router.push(searchPath(example));
  }

  function loadMore() {
    setLoading(true);
    setPage({ query, limit: Math.min(limit + PAGE_SIZE, MAX_K) });
  }

  return (
    <div>
      <form role="search" onSubmit={onSubmit} className="flex gap-2">
        <label htmlFor="moment-search" className="sr-only">
          Search moments
        </label>
        <input
          id="moment-search"
          type="search"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="the part where he parks the bike at night"
          autoComplete="off"
          spellCheck={false}
          className="h-11 w-full rounded-lg border border-white/10 bg-zinc-900/60 px-3.5 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-white/30 focus:outline-none"
        />
        <button
          type="submit"
          className="h-11 shrink-0 rounded-lg bg-zinc-100 px-4 text-sm font-medium text-zinc-950 transition hover:bg-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white/70"
        >
          Search
        </button>
      </form>

      <div className="mt-6 min-h-[32rem]" aria-live="polite" aria-busy={loading}>
        {!query ? (
          <IdleState onExample={searchExample} />
        ) : !payload && error ? (
          <ErrorState title="The search index is unavailable" message={error} onRetry={retry} />
        ) : !payload ? (
          <SkeletonGrid />
        ) : results.length === 0 ? (
          <EmptyResults query={query} />
        ) : (
          <>
            <p className="mb-4 text-xs text-zinc-500">
              {results.length} {results.length === 1 ? "moment" : "moments"} for “{query}”
            </p>
            <ResultsGrid moments={results} assetNames={assetNames} />
            {error ? (
              <div className="mt-8 flex flex-wrap items-center justify-center gap-3 text-sm text-red-300">
                <span>{error}</span>
                <button
                  type="button"
                  onClick={retry}
                  className="rounded-lg border border-red-400/30 px-3 py-1.5 text-xs font-medium text-red-100 transition hover:border-red-300/60 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-300"
                >
                  Try again
                </button>
              </div>
            ) : results.length >= limit && limit < MAX_K ? (
              <div className="mt-8 flex justify-center">
                <button
                  type="button"
                  disabled={loading}
                  onClick={loadMore}
                  className="rounded-lg border border-white/15 px-4 py-2 text-sm text-zinc-300 transition hover:border-white/30 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white/70 disabled:opacity-50"
                >
                  {loading ? "Loading…" : "Load more"}
                </button>
              </div>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
