"use client";

import Link from "next/link";
import { Show, UserButton } from "@clerk/nextjs";
import { useState } from "react";

export default function Navbar() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <nav className="fixed top-6 left-1/2 -translate-x-1/2 z-40 w-max">
        <div className="glass rounded-full px-6 py-3 flex items-center gap-8 backdrop-blur-2xl">
          <Link href="/" className="flex items-center">
            <span className="text-sm font-light tracking-[0.25em] text-foreground uppercase">Igloo</span>
          </Link>

          <div className="hidden md:flex items-center gap-6 text-sm text-text-secondary">
            <a href="#how-it-works" className="transition-colors duration-300 hover:text-foreground">
              How it works
            </a>
            <a href="#features" className="transition-colors duration-300 hover:text-foreground">
              Features
            </a>
            <a href="#pricing" className="transition-colors duration-300 hover:text-foreground">
              Pricing
            </a>
          </div>

          <div className="hidden md:flex items-center gap-3">
            <Show when="signed-out">
              <Link href="/sign-in" className="text-sm text-text-secondary hover:text-foreground transition-colors duration-300">
                Sign in
              </Link>
              <Link href="/sign-up" className="btn-primary !py-2 !px-5 !text-sm">
                Get started
              </Link>
            </Show>
            <Show when="signed-in">
              <Link href="/create" className="btn-primary !py-2 !px-5 !text-sm">
                Create a video
              </Link>
              <UserButton />
            </Show>
          </div>

          {/* Mobile hamburger */}
          <button
            onClick={() => setOpen(!open)}
            className="md:hidden relative w-6 h-5 flex flex-col justify-between"
            aria-label="Menu"
          >
            <span
              className={`block h-px w-full bg-foreground transition-all duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] origin-center ${
                open ? "rotate-45 translate-y-[9px]" : ""
              }`}
            />
            <span
              className={`block h-px w-full bg-foreground transition-all duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] ${
                open ? "opacity-0 scale-x-0" : ""
              }`}
            />
            <span
              className={`block h-px w-full bg-foreground transition-all duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] origin-center ${
                open ? "-rotate-45 -translate-y-[9px]" : ""
              }`}
            />
          </button>
        </div>
      </nav>

      {/* Mobile overlay */}
      <div
        className={`fixed inset-0 z-30 backdrop-blur-3xl bg-background/90 flex flex-col items-center justify-center gap-8 transition-all duration-700 ease-[cubic-bezier(0.32,0.72,0,1)] ${
          open ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        }`}
      >
        {["How it works", "Features", "Pricing"].map((label, i) => (
          <a
            key={label}
            href={`#${label.toLowerCase().replace(/ /g, "-")}`}
            onClick={() => setOpen(false)}
            className="text-3xl font-light tracking-tight text-foreground transition-all duration-600"
            style={{
              transitionDelay: open ? `${i * 80}ms` : "0ms",
              opacity: open ? 1 : 0,
              transform: open ? "translateY(0)" : "translateY(2rem)",
            }}
          >
            {label}
          </a>
        ))}

        <div
          className="mt-4 flex flex-col items-center gap-4 transition-all duration-600"
          style={{
            transitionDelay: open ? "240ms" : "0ms",
            opacity: open ? 1 : 0,
            transform: open ? "translateY(0)" : "translateY(2rem)",
          }}
        >
          <Show when="signed-out">
            <Link href="/sign-up" className="btn-primary" onClick={() => setOpen(false)}>
              Get started
            </Link>
            <Link href="/sign-in" className="btn-secondary" onClick={() => setOpen(false)}>
              Sign in
            </Link>
          </Show>
          <Show when="signed-in">
            <Link href="/create" className="btn-primary" onClick={() => setOpen(false)}>
              Create a video
            </Link>
          </Show>
        </div>
      </div>
    </>
  );
}
