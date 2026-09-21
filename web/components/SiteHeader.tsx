import Link from "next/link";

export default function SiteHeader() {
  return (
    <header className="border-b border-white/10">
      <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-4">
        <Link
          href="/"
          className="text-sm font-semibold tracking-tight text-zinc-100 transition hover:text-white"
        >
          shotgrep
        </Link>
        <span className="text-xs text-zinc-500">Search video like it&apos;s text</span>
      </div>
    </header>
  );
}
