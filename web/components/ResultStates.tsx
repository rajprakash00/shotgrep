import type { ReactNode } from "react";

import { BUTTON_SMALL } from "@/components/buttonStyles";

const EXAMPLES = [
  "a rabbit sleeping inside a burrow",
  "a dragon flying over a city at sunset",
  "a robot hand reaching for a young man's face",
  "a ruined city after a machine uprising",
];

function NoticeCard({
  title,
  message,
  action,
  danger,
  children,
}: {
  title: string;
  message: string;
  action?: { label: string; onClick: () => void };
  danger?: boolean;
  children?: ReactNode;
}) {
  return (
    <div
      role={danger ? "alert" : undefined}
      className={`border border-dashed bg-card/70 p-8 ${
        danger ? "border-stamp" : "border-rule"
      }`}
    >
      <h2 className={`font-display text-xl ${danger ? "text-stamp" : ""}`}>{title}</h2>
      <p className="mt-2 max-w-xl text-sm leading-relaxed text-ink-soft">{message}</p>
      {action ? (
        <button
          type="button"
          onClick={action.onClick}
          className={`mt-5 ${BUTTON_SMALL}`}
        >
          {action.label}
        </button>
      ) : null}
      {children}
    </div>
  );
}

export function IdleState({ onExample }: { onExample: (example: string) => void }) {
  return (
    <NoticeCard
      title="Ask for a moment in plain language"
      message="Transcript and visual search are fused, so quoted speech and described scenes both land in the same catalog."
    >
      <ul className="mt-5 flex flex-wrap items-center gap-2">
        <li className="font-code text-[11px] uppercase tracking-[0.18em] text-ink-soft">
          From the card catalog
        </li>
        {EXAMPLES.map((example) => (
          <li key={example}>
            <button
              type="button"
              onClick={() => onExample(example)}
              className="border border-ink/60 bg-paper-deep px-2.5 py-1 text-xs shadow-chip transition hover:border-ink hover:shadow-chip-hover"
            >
              {example}
            </button>
          </li>
        ))}
      </ul>
    </NoticeCard>
  );
}

export function EmptyResults({ query }: { query: string }) {
  return (
    <NoticeCard
      title={`No moments matched “${query}”`}
      message="Try a shorter phrase, or describe what is on screen rather than what is said."
    />
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
    <NoticeCard danger title={title} message={message} action={{ label: "Try again", onClick: onRetry }} />
  );
}

export function SkeletonGrid() {
  return (
    <ul aria-hidden className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }, (_, index) => (
        <li key={index} className="border border-rule bg-card">
          <div className="aspect-video animate-pulse bg-paper-deep" />
          <div className="space-y-2 border-t border-rule p-3.5">
            <div className="h-3 w-28 animate-pulse bg-paper-deep" />
            <div className="h-3 w-full animate-pulse bg-paper-deep" />
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
    <div className="flex aspect-video w-full flex-col items-center justify-center gap-2 border border-dashed border-rule bg-card/70 px-6 text-center">
      <p className="font-display text-xl">{title}</p>
      <p className="max-w-md text-sm leading-relaxed text-ink-soft">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className={`mt-3 ${BUTTON_SMALL}`}
        >
          Try again
        </button>
      ) : null}
    </div>
  );
}
