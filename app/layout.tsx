import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "MusicLibrary — Audio Asset Manager",
  description: "Complete audio asset manager with track indexing, search, and export for video production pipeline.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
