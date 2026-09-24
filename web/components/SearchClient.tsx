"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { EmptyResults, ErrorState, IdleState, SkeletonGrid } from "@/components/ResultStates";
import ResultsGrid from "@/components/ResultsGrid";
import { BUTTON_DANGER, BUTTON_PRIMARY, BUTTON_SECONDARY } from "@/components/buttonStyles";
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
      <form role="search" onSubmit={onSubmit} className="mt-7 flex max-w-3xl items-stretch gap-3">
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
          className="h-12 w-full border border-ink bg-card px-3.5 font-code text-sm shadow-input transition placeholder:text-ink-soft focus:border-stamp focus:shadow-input-focus"
        />
        <button type="submit" className={BUTTON_PRIMARY}>
          Search
        </button>
      </form>

      <div className="perforation mt-10" aria-hidden />

      <div className="mt-10 min-h-[24rem]" aria-live="polite" aria-busy={loading}>
        {!query ? (
          <IdleState onExample={searchExample} />
        ) : !payload && error ? (
          <ErrorState title="The index could not be reached" message={error} onRetry={retry} />
        ) : !payload ? (
          <SkeletonGrid />
        ) : results.length === 0 ? (
          <EmptyResults query={query} />
        ) : (
          <>
            <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-ink pb-2">
              <p className="font-code text-xs uppercase tracking-[0.2em]">
                {results.length} {results.length === 1 ? "moment" : "moments"} for “{query}”
              </p>
              <p className="font-code text-[11px] uppercase tracking-[0.16em] text-ink-soft">
                ranked by fused score
              </p>
            </div>
            <div className="mt-6">
              <ResultsGrid moments={results} assetNames={assetNames} />
            </div>
            {error ? (
              <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
                <span className="font-code text-xs text-stamp">{error}</span>
                <button type="button" onClick={retry} className={BUTTON_DANGER}>
                  Try again
                </button>
              </div>
            ) : results.length >= limit && limit < MAX_K ? (
              <div className="mt-10 flex justify-center">
                <button
                  type="button"
                  disabled={loading}
                  onClick={loadMore}
                  className={BUTTON_SECONDARY}
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
