import Link from "next/link";

import SiteHeader from "@/components/SiteHeader";
import WatchClient from "@/components/WatchClient";
import { parseStartSeconds } from "@/lib/urls";

export default async function WatchPage({ params, searchParams }: PageProps<"/watch/[assetId]">) {
  const { assetId } = await params;
  const { t } = await searchParams;

  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-4xl px-6 pb-24 pt-8">
        <Link href="/" className="text-xs text-zinc-500 transition hover:text-zinc-300">
          ← Back to search
        </Link>
        <WatchClient key={assetId} assetId={assetId} startSeconds={parseStartSeconds(t)} />
      </main>
    </>
  );
}
