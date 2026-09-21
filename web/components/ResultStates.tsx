const EXAMPLES = [
  "a rabbit sleeping inside a burrow",
  "a dragon flying over a city at sunset",
  "a robot hand reaching for a young man's face",
  "a ruined city after a machine uprising",
];

export function IdleState({ onExample }: { onExample: (example: string) => void }) {
  return (
    <div className="rounded-xl border border-dashed border-white/10 bg-zinc-900/20 p-8">
      <h2 className="text-sm font-medium text-zinc-300">Ask for a moment in plain language</h2>
      <p className="mt-1 text-sm text-zinc-500">
        Transcript and visual search are fused, so quoted speech and described scenes both work.
      </p>
      <ul className="mt-5 flex flex-wrap gap-2">
        {EXAMPLES.map((example) => (
          <li key={example}>
            <button
              type="button"
              onClick={() => onExample(example)}
              className="rounded-full border border-white/10 bg-zinc-900/60 px-3 py-1.5 text-xs text-zinc-400 transition hover:border-white/25 hover:text-zinc-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white/70"
            >
              {example}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function EmptyResults({ query }: { query: string }) {
  return (
    <div className="rounded-xl border border-dashed border-white/10 bg-zinc-900/20 p-8">
      <h2 className="text-sm font-medium text-zinc-300">No moments matched “{query}”</h2>
      <p className="mt-1 text-sm text-zinc-500">
        Try a shorter phrase, or describe what is on screen rather than what is said.
      </p>
    </div>
  );
}

export function ErrorState({
  title,
  message,
  onRetry,
}: {
  title: string;
  message: string;
  onRetry: () => void;
}) {
  return (
    <div
      role="alert"
      className="rounded-xl border border-red-500/20 bg-red-500/5 p-8 text-sm text-red-200"
    >
      <h2 className="font-medium">{title}</h2>
      <p className="mt-1 text-red-200/80">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 rounded-lg border border-red-400/30 px-3 py-1.5 text-xs font-medium text-red-100 transition hover:border-red-300/60 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-300"
      >
        Try again
      </button>
    </div>
  );
}

export function SkeletonGrid() {
  return (
    <ul aria-hidden className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }, (_, index) => (
        <li key={index} className="overflow-hidden rounded-xl border border-white/10 bg-zinc-900/40">
          <div className="aspect-video animate-pulse bg-zinc-800/60" />
          <div className="space-y-2 p-3">
            <div className="h-3 w-24 animate-pulse rounded bg-zinc-800" />
            <div className="h-3 w-full animate-pulse rounded bg-zinc-800" />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function PlayerMessage({
  title,
  message,
  onRetry,
}: {
  title: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex aspect-video w-full flex-col items-center justify-center gap-2 rounded-xl border border-white/10 bg-zinc-900/60 px-6 text-center">
      <p className="text-sm font-medium text-zinc-300">{title}</p>
      <p className="max-w-md text-sm text-zinc-500">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:border-white/35 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white/70"
        >
          Try again
        </button>
      ) : null}
    </div>
  );
}
