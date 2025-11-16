export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
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
  );
}
