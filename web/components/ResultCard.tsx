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
      className="group flex h-full flex-col overflow-hidden rounded-xl border border-white/10 bg-zinc-900/40 transition hover:border-white/25 hover:bg-zinc-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white/70"
    >
      <div className="relative aspect-video overflow-hidden bg-zinc-800/60">
        <img
          src={moment.thumbnail_url}
          alt=""
          loading="lazy"
          decoding="async"
          className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.02]"
        />
        <span className="absolute left-2 top-2 rounded bg-black/70 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-zinc-300">
          {KIND_LABELS[moment.kind]}
        </span>
        <span className="absolute bottom-2 left-2 rounded bg-black/80 px-1.5 py-0.5 font-mono text-xs tabular-nums text-white">
          {formatTimestamp(moment.start_s)}
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-1.5 p-3">
        <p className="truncate text-[11px] uppercase tracking-wider text-zinc-500">
          {assetName ?? moment.asset_id.slice(0, 12)}
        </p>
        <p className="line-clamp-2 text-sm leading-snug text-zinc-300">
          {moment.snippet ? `“${moment.snippet}”` : "Visual match"}
        </p>
      </div>
    </Link>
  );
}
