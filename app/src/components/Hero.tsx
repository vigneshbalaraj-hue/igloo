"use client";

import Link from "next/link";
import { Show } from "@clerk/nextjs";
import { useRef, useEffect } from "react";

export default function Hero() {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    videoRef.current?.play().catch(() => {});
  }, []);

  return (
    <section className="relative z-20 min-h-[100dvh] flex items-center justify-center overflow-hidden isolate">
      {/* Video background — WebM (VP9) primary, MP4 (h264) fallback, poster while loading */}
      <video
        ref={videoRef}
        autoPlay
        muted
        loop
        playsInline
        poster="/hero-poster.jpg"
        className="absolute inset-0 z-0 w-full h-full object-cover"
      >
        <source src="/hero-bg.mp4" type="video/mp4" />
        <source src="/hero-bg.webm" type="video/webm" />
      </video>

      {/* Inward vignette mask — radial fade from center to all edges */}
      <div
        className="absolute inset-0 z-[1] pointer-events-none"
        style={{
          background: [
            "radial-gradient(ellipse 70% 55% at center, transparent 0%, rgba(5,5,5,0.15) 40%, rgba(5,5,5,0.55) 65%, rgba(5,5,5,0.85) 80%, #050505 100%)",
          ].join(", "),
        }}
      />

      {/* Top fade for navbar blend */}
      <div className="absolute inset-x-0 top-0 h-40 z-[2] bg-gradient-to-b from-[#050505] via-[#050505]/60 to-transparent pointer-events-none" />

      {/* Bottom fade for section transition */}
      <div className="absolute inset-x-0 bottom-0 h-52 z-[2] bg-gradient-to-t from-[#050505] via-[#050505]/70 to-transparent pointer-events-none" />

      {/* Left edge fade */}
      <div className="absolute inset-y-0 left-0 w-32 z-[2] bg-gradient-to-r from-[#050505]/80 to-transparent pointer-events-none" />

      {/* Right edge fade */}
      <div className="absolute inset-y-0 right-0 w-32 z-[2] bg-gradient-to-l from-[#050505]/80 to-transparent pointer-events-none" />

      {/* Content — centered */}
      <div className="relative z-10 text-center max-w-3xl mx-auto px-6 flex flex-col items-center justify-center hero-text-shadow">
        <div className="eyebrow justify-center mb-8 border-accent-bright/30 text-accent-bright">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent-bright animate-pulse" />
          Now in beta
        </div>

        <h1 className="text-4xl md:text-6xl lg:text-7xl font-light tracking-tight leading-none text-foreground">
          Video that
          <br />
          stops thumbs.
        </h1>

        <p className="mt-6 text-base md:text-lg text-foreground font-medium tracking-[0.15em]">
          Unscrollable <span className="text-foreground/40 mx-2">·</span> Cinematic <span className="text-foreground/40 mx-2">·</span> Niche-proof
        </p>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
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

        <p className="mt-6 text-sm text-foreground/50">
          2 videos for <span className="text-foreground font-medium">$14.99</span>{" "}
          <span className="text-foreground/50">·</span>{" "}
          or <span className="text-foreground/70">$9.99</span> each
        </p>
      </div>
    </section>
  );
}
