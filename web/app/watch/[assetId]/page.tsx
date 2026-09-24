import Link from "next/link";

import SiteFooter from "@/components/SiteFooter";
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
        <Link
          href="/"
          className="font-code text-[11px] uppercase tracking-[0.16em] text-ink-soft underline decoration-rule underline-offset-4 transition hover:decoration-stamp"
        >
          ← Back to search
        </Link>
        <WatchClient key={assetId} assetId={assetId} startSeconds={parseStartSeconds(t)} />
      </main>
      <SiteFooter />
    </>
  );
}
