import Navbar from "@/components/Navbar";

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <div className="mesh-gradient" />
      <div className="noise-overlay" />
      <Navbar />
      <main className="relative z-10 min-h-screen pt-32 pb-24 px-6 md:px-12">
        <div className="policy-content max-w-[760px] mx-auto">
          {children}
        </div>
      </main>
      <footer className="relative z-10 border-t border-border-subtle py-12">
        <div className="max-w-[1400px] mx-auto px-6 md:px-12 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-6">
            <a href="/" className="text-sm font-light tracking-[0.2em] uppercase text-foreground hover:text-accent-bright transition-colors duration-300">
              Igloo
            </a>
            <span className="text-xs text-text-muted">
              Video that stops thumbs.
            </span>
          </div>
          <div className="flex items-center gap-6 text-xs text-text-muted">
            <a href="/privacy" className="hover:text-foreground transition-colors duration-300">Privacy</a>
            <a href="/terms" className="hover:text-foreground transition-colors duration-300">Terms</a>
            <a href="/refund" className="hover:text-foreground transition-colors duration-300">Refunds</a>
            <a href="/contact" className="hover:text-foreground transition-colors duration-300">Contact</a>
          </div>
        </div>
      </footer>
    </>
  );
}
