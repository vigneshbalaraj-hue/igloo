export default function Footer() {
  return (
    <footer className="relative z-10 border-t border-border-subtle py-12">
      <div className="max-w-[1400px] mx-auto px-6 md:px-12 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-6">
          <span className="text-sm font-light tracking-[0.2em] uppercase text-foreground">
            Igloo
          </span>
          <span className="text-xs text-text-muted">
            Video that stops thumbs.
          </span>
        </div>

        <div className="flex items-center gap-6 text-xs text-text-muted">
          <a href="#how-it-works" className="hover:text-foreground transition-colors duration-300">How it works</a>
          <a href="#features" className="hover:text-foreground transition-colors duration-300">Features</a>
          <a href="#showcase" className="hover:text-foreground transition-colors duration-300">Showcase</a>
          <a href="https://www.instagram.com/igloo.video/" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors duration-300" aria-label="Instagram">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
              <circle cx="12" cy="12" r="5" />
              <circle cx="17.5" cy="6.5" r="1.5" fill="currentColor" stroke="none" />
            </svg>
          </a>
        </div>

        <div className="flex items-center gap-6 text-xs text-text-muted mt-4 md:mt-0">
          <a href="/privacy" className="hover:text-foreground transition-colors duration-300">Privacy</a>
          <a href="/terms" className="hover:text-foreground transition-colors duration-300">Terms</a>
          <a href="/refund" className="hover:text-foreground transition-colors duration-300">Refunds</a>
          <a href="/contact" className="hover:text-foreground transition-colors duration-300">Contact</a>
        </div>
      </div>
    </footer>
  );
}
