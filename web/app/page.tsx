import SearchClient from "@/components/SearchClient";
import SiteHeader from "@/components/SiteHeader";

export default async function Home({ searchParams }: PageProps<"/">) {
  const params = await searchParams;
  const query = typeof params.q === "string" ? params.q.trim() : "";

  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-5xl px-6 pb-24">
        <section className="pb-8 pt-14">
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Search video like it&apos;s text.
          </h1>
          <p className="mt-3 max-w-xl text-sm text-zinc-400">
            Ask for a moment in plain language and open the exact frame. Visual and transcript
            retrieval are fused, with deep links that survive a reload.
          </p>
        </section>
        <SearchClient key={query} query={query} />
      </main>
    </>
  );
}
