import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Vastu Plan Analyzer",
  description: "Analyse a floor plan against a Vastu rule set.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Newsreader:opsz,wght@6..72,400;6..72,500&display=swap"
        />
      </head>
      <body className="min-h-screen font-sans text-[15px]">{children}</body>
    </html>
  );
}
