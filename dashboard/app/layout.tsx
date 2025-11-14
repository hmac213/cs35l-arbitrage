import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Arbitrage Dashboard",
  description: "Live view of current and historical arbitrage opportunities.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-zinc-950 text-zinc-50`}
      >
        <div className="min-h-screen flex flex-col">
          <header className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur">
            <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
              <div className="space-y-1">
                <h1 className="text-lg font-semibold tracking-tight">
                  Arbitrage Dashboard
                </h1>
                <p className="text-xs text-zinc-400">
                  Visualize current and historical opportunities across exchanges.
                </p>
              </div>
              <div className="text-xs text-zinc-500">
                Powered by /api/get_paired_markets
              </div>
            </div>
          </header>
          <main className="mx-auto flex w-full max-w-6xl flex-1 px-4 py-6">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}

