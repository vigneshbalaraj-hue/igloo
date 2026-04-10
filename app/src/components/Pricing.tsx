"use client";

import { useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { Show } from "@clerk/nextjs";
import ScrollReveal from "./ScrollReveal";
import { PRICING_TIERS } from "@/lib/pricing";

const reels = [
  "/reels/fasting-wellness.mp4",
  "/reels/hanuman-lanka.mp4",
  "/reels/spiritual-growth.mp4",
  "/reels/igloo-promo.mp4",
];

// Interleaved pattern: same video repeats only after 3 others.
// Pattern [0,1,2,3,0,1,2,3] maintains 4-gap rule even across the loop seam.
// Staggered offsets so same-source copies don't show identical frames.
const trackItems = [
  { src: reels[0], offset: 0 },
  { src: reels[1], offset: 0 },
  { src: reels[2], offset: 0 },
  { src: reels[3], offset: 0 },
  { src: reels[0], offset: 15 },
  { src: reels[1], offset: 20 },
  { src: reels[2], offset: 18 },
  { src: reels[3], offset: 25 },
];

// Duplicate for seamless infinite CSS loop (translateX -50%)
const fullTrack = [...trackItems, ...trackItems];

export default function Pricing() {
  const videoRefs = useRef<(HTMLVideoElement | null)[]>([]);

  const setRef = useCallback(
    (index: number) => (el: HTMLVideoElement | null) => {
      videoRefs.current[index] = el;
    },
    [],
  );

  const marqueeRef = useRef<HTMLDivElement>(null);

  /* Apply currentTime offsets for staggered playback */
  useEffect(() => {
    videoRefs.current.forEach((video, i) => {
      if (!video) return;
      const offset = fullTrack[i].offset;
      if (offset === 0) return;
      const apply = () => {
        video.currentTime = offset;
      };
      if (video.readyState >= 1) {
        apply();
      } else {
        video.addEventListener("loadedmetadata", apply, { once: true });
      }
    });
  }, []);

  /* Lazy video activation — only play/load videos when marquee is in viewport.
     Prevents iOS from choking on 16 simultaneous video decoders. */
  useEffect(() => {
    const marquee = marqueeRef.current;
    if (!marquee) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        videoRefs.current.forEach((video) => {
          if (!video) return;
          if (entry.isIntersecting) {
            video.src = video.dataset.src || "";
            video.play().catch(() => {});
          } else {
            video.pause();
            video.removeAttribute("src");
            video.load();
          }
        });
      },
      { rootMargin: "200px 0px" },
    );

    observer.observe(marquee);
    return () => observer.disconnect();
  }, []);

  return (
    <section id="pricing" className="relative z-10 py-28 md:py-40">
      <div className="max-w-[1400px] mx-auto px-6 md:px-12">
        <ScrollReveal>
          <div className="text-center max-w-2xl mx-auto">
            <span className="eyebrow mb-6 mx-auto">Pricing</span>
            <h2 className="text-3xl md:text-5xl font-light tracking-tight leading-tight mt-4 sr-only">
              Pricing
            </h2>
          </div>
        </ScrollReveal>

        {/* Reel marquee — horizontal auto-scrolling showcase */}
        <ScrollReveal className="mt-12">
          <div ref={marqueeRef} className="reel-marquee-mask overflow-hidden">
            <div className="reel-marquee-track">
              {fullTrack.map((item, i) => (
                <div
                  key={i}
                  className="shrink-0 w-[180px] md:w-[220px] aspect-[9/16] rounded-2xl overflow-hidden"
                >
                  <video
                    ref={setRef(i)}
                    data-src={item.src}
                    muted
                    loop
                    playsInline
                    className="w-full h-full object-cover"
                  />
                </div>
              ))}
            </div>
          </div>
        </ScrollReveal>

        <ScrollReveal className="mt-16 max-w-lg mx-auto">
          <div className="group rounded-[2rem] border border-border-subtle bg-surface p-10 md:p-12 transition-all duration-700 ease-[cubic-bezier(0.32,0.72,0,1)] hover:border-border-hover hover:bg-surface-elevated">
              <div className="flex items-center gap-3 mb-1">
                <span className="eyebrow">{PRICING_TIERS.double.badge}</span>
              </div>
              <div className="flex items-baseline gap-3">
                <span className="text-5xl md:text-6xl font-light tracking-tight text-foreground">
                  ${PRICING_TIERS.double.display_usd}
                </span>
                <span className="text-text-muted text-sm">for {PRICING_TIERS.double.label}</span>
              </div>
              <p className="mt-2 text-text-muted text-sm">
                or ${PRICING_TIERS.single.display_usd} for {PRICING_TIERS.single.label}
              </p>

              <p className="mt-4 text-text-secondary text-sm leading-relaxed">
                Beta pricing. Closing soon.
              </p>

              <ul className="mt-8 space-y-4">
                {[
                  "40 to 60 second cinematic video",
                  "Script that actually says something",
                  "Original visuals. No stock footage.",
                  "Netflix documentary narration",
                  "Every video drives to a next step",
                  "MP4 delivered in minutes",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-3 text-sm text-text-secondary">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-accent mt-0.5 shrink-0"><polyline points="20 6 9 17 4 12"/></svg>
                    {item}
                  </li>
                ))}
              </ul>

              <div className="mt-10">
                <Show when="signed-out">
                  <Link href="/sign-up" className="btn-primary w-full justify-center">
                    Get your first video
                    <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-black/10">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
                    </span>
                  </Link>
                </Show>
                <Show when="signed-in">
                  <Link href="/create" className="btn-primary w-full justify-center">
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
