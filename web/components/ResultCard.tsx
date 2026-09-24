import Link from "next/link";

import { formatTimestamp } from "@/lib/format";
import type { Moment, MomentKind } from "@/lib/types";
import { deepLinkPath } from "@/lib/urls";

const KIND_LABELS: Record<MomentKind, string> = {
  frame: "frame",
  shot_start: "shot start",
  transcript: "speech",
};

export default function ResultCard({ moment, assetName }: { moment: Moment; assetName?: string }) {
  const href = deepLinkPath(moment.deep_link) ?? `/watch/${moment.asset_id}?t=${moment.start_s}`;
  return (
    <Link
      href={href}
      className="group flex h-full flex-col border border-ink/80 bg-card shadow-card transition duration-150 hover:-translate-y-0.5 hover:shadow-card-hover"
    >
      <div className="relative border-b border-rule">
        <img
          src={moment.thumbnail_url}
          alt=""
          loading="lazy"
          decoding="async"
          className="aspect-video w-full object-cover"
        />
        <span className="absolute bottom-0 right-0 border-l border-t border-rule bg-card px-2 py-0.5 font-code text-[11px] tabular-nums">
          {formatTimestamp(moment.start_s)}
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-2 p-3.5">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate font-display text-sm italic">
            {assetName ?? moment.asset_id.slice(0, 12)}
          </span>
          <span className="-rotate-1 shrink-0 border border-stamp px-1.5 py-0.5 font-code text-[10px] uppercase tracking-[0.16em] text-stamp">
            {KIND_LABELS[moment.kind]}
          </span>
        </div>
        <p className="line-clamp-2 text-sm leading-snug text-ink-soft">
          {moment.snippet ? `“${moment.snippet}”` : "Visual match"}
        </p>
      </div>
    </Link>
  );
}
