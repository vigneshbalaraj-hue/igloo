import Link from "next/link";
import { Show } from "@clerk/nextjs";
import ScrollReveal from "./ScrollReveal";

export default function FinalCTA() {
  return (
    <section className="relative z-10 py-28 md:py-40">
      <div className="max-w-[1400px] mx-auto px-6 md:px-12">
        <ScrollReveal>
          <div className="relative rounded-[2rem] border border-border-subtle bg-surface overflow-hidden px-8 py-20 md:px-16 md:py-28 text-center transition-all duration-700 ease-[cubic-bezier(0.32,0.72,0,1)] hover:border-border-hover hover:bg-surface-elevated">
              {/* Subtle glow */}
              <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[400px] h-[200px] bg-accent/10 blur-[100px] rounded-full pointer-events-none" />

              <h2 className="relative text-3xl md:text-5xl font-light tracking-tight leading-tight text-foreground">
                Your audience is scrolling.<br />
                Make them stop.
              </h2>
              <p className="relative mt-4 text-text-secondary text-base md:text-lg max-w-[45ch] mx-auto">
                Join the beta. Get a video that actually says something.
              </p>

              <div className="relative mt-10 flex flex-wrap justify-center gap-4">
                <Show when="signed-out">
                  <Link href="/sign-up" className="btn-primary">
                    Start creating
                    <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-black/10">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
                    </span>
                  </Link>
                </Show>
                <Show when="signed-in">
                  <Link href="/create" className="btn-primary">
                    Create a video
                    <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-black/10">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
                    </span>
                  </Link>
                </Show>
              </div>
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}
