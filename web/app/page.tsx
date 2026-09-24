import SearchClient from "@/components/SearchClient";
import SiteFooter from "@/components/SiteFooter";
import SiteHeader from "@/components/SiteHeader";

export default async function Home({ searchParams }: PageProps<"/">) {
  const params = await searchParams;
  const query = typeof params.q === "string" ? params.q.trim() : "";

  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-6xl px-6 pb-20">
        <section className="pt-12">
          <p className="font-code text-[11px] uppercase tracking-[0.22em] text-ink-soft">
            A search index for footage
          </p>
          <h1 className="mt-3 max-w-3xl font-display text-4xl font-semibold leading-[1.05] sm:text-5xl">
            Search video like it&rsquo;s <em>text</em>.
          </h1>
          <p className="mt-4 max-w-xl text-sm leading-relaxed text-ink-soft">
            Describe a scene, or quote a line. Visual and transcript retrieval are fused, and
            every card opens at its timecode.
          </p>
          <SearchClient key={query} query={query} />
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
