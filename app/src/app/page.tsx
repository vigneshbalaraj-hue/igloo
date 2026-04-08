import Link from "next/link";
import { Show, UserButton } from "@clerk/nextjs";

export default function Home() {
  return (
    <main className="flex-1 flex flex-col items-center justify-center px-6 text-center">
      <h1 className="text-5xl sm:text-7xl font-semibold tracking-tight">
        Igloo
      </h1>
      <p className="mt-4 text-xl text-neutral-400 max-w-xl">
        Video that stops thumbs. Type a topic, get a finished reel overnight.
      </p>

      <div className="mt-10 flex items-center gap-4">
        <Show when="signed-out">
          <Link
            href="/sign-up"
            className="rounded-full bg-white text-black px-6 py-3 font-medium hover:bg-neutral-200 transition"
          >
            Get started
          </Link>
          <Link
            href="/sign-in"
            className="rounded-full border border-neutral-700 px-6 py-3 font-medium hover:bg-neutral-900 transition"
          >
            Sign in
          </Link>
        </Show>

        <Show when="signed-in">
          <Link
            href="/create"
            className="rounded-full bg-white text-black px-6 py-3 font-medium hover:bg-neutral-200 transition"
          >
            Create a reel
          </Link>
          <UserButton />
        </Show>
      </div>
    </main>
  );
}
