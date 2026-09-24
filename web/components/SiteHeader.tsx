import Link from "next/link";

import { apiBaseUrl } from "@/lib/config";

export default function SiteHeader() {
  const api = apiBaseUrl();

  return (
    <header className="border-b-2 border-ink">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-baseline justify-between gap-x-6 gap-y-1 px-6 py-3">
        <Link href="/" className="font-display text-lg font-semibold tracking-tight">
          shotgrep
        </Link>
        <p className="order-3 font-code text-[11px] uppercase tracking-[0.18em] text-ink-soft sm:order-2">
          moment search over the corpus
        </p>
        <nav className="order-2 flex gap-5 font-code text-[11px] uppercase tracking-[0.18em] sm:order-3">
          <a
            href={`${api}/docs`}
            className="underline decoration-rule underline-offset-4 transition hover:decoration-stamp"
          >
            rest
          </a>
          <span className="group relative inline-block">
            <a
              href={`${api}/mcp`}
              aria-describedby="mcp-hint"
              className="underline decoration-rule underline-offset-4 transition hover:decoration-stamp"
            >
              mcp
            </a>
            <span
              id="mcp-hint"
              role="tooltip"
              className="pointer-events-none absolute right-0 top-full z-10 mt-2 w-60 border border-ink bg-card px-3 py-2 text-left font-code text-[10px] normal-case leading-relaxed tracking-[0.04em] text-ink-soft opacity-0 shadow-chip transition-opacity group-hover:opacity-100 group-focus-within:opacity-100"
            >
              MCP endpoint for agent clients. A browser cannot open it directly.
            </span>
          </span>
        </nav>
      </div>
    </header>
  );
}
