import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "shotgrep",
  description: "Search video like it's text.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body className="min-h-dvh bg-zinc-950 font-sans text-zinc-100 antialiased">{children}</body>
    </html>
  );
}
