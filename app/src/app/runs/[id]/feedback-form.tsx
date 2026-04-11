"use client";

import { useEffect, useState } from "react";

function Star({
  filled,
  hovered,
  onClick,
  onMouseEnter,
  onMouseLeave,
}: {
  filled: boolean;
  hovered: boolean;
  onClick: () => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      className="p-0.5 transition-colors"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill={filled || hovered ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth={1.5}
        className={`h-8 w-8 ${
          filled
            ? "text-yellow-400"
            : hovered
              ? "text-yellow-400/60"
              : "text-neutral-600"
        }`}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z"
        />
      </svg>
    </button>
  );
}

function ReadOnlyStars({ rating }: { rating: number }) {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => (
        <svg
          key={i}
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill={i <= rating ? "currentColor" : "none"}
          stroke="currentColor"
          strokeWidth={1.5}
          className={`h-6 w-6 ${
            i <= rating ? "text-yellow-400" : "text-neutral-600"
          }`}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z"
          />
        </svg>
      ))}
    </div>
  );
}

export default function FeedbackForm({ runId }: { runId: string }) {
  const [rating, setRating] = useState<number | null>(null);
  const [hoveredStar, setHoveredStar] = useState<number | null>(null);
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [existingRating, setExistingRating] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/runs/${runId}/feedback`)
      .then((r) => r.json())
      .then((data) => {
        if (data.feedback) {
          setExistingRating(data.feedback.rating);
          setSubmitted(true);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [runId]);

  async function handleSubmit() {
    if (!rating || submitting) return;
    setSubmitting(true);
    setError(null);

    try {
      const res = await fetch(`/api/runs/${runId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating, comment }),
      });

      if (res.status === 409) {
        setSubmitted(true);
        setExistingRating(rating);
        return;
      }

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Failed to submit feedback");
      }

      setSubmitted(true);
      setExistingRating(rating);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return null;

  if (submitted) {
    return (
      <div className="rounded-xl border border-neutral-800 bg-neutral-900 px-5 py-4">
        <div className="flex items-center gap-3">
          <ReadOnlyStars rating={existingRating ?? 0} />
          <span className="text-sm text-neutral-400">
            Thanks for your feedback!
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900 px-5 py-5">
      <p className="text-sm font-medium text-neutral-300 mb-3">
        How was your reel?
      </p>

      <div className="flex gap-0.5 mb-4">
        {[1, 2, 3, 4, 5].map((i) => (
          <Star
            key={i}
            filled={rating !== null && i <= rating}
            hovered={hoveredStar !== null && i <= hoveredStar}
            onClick={() => setRating(i)}
            onMouseEnter={() => setHoveredStar(i)}
            onMouseLeave={() => setHoveredStar(null)}
          />
        ))}
      </div>

      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Any thoughts? (optional)"
        rows={3}
        maxLength={2000}
        className="w-full rounded-lg bg-neutral-950 border border-neutral-800 px-4 py-3 text-sm text-neutral-200 placeholder:text-neutral-600 focus:outline-none focus:border-neutral-600 resize-none"
      />

      {error && (
        <p className="mt-2 text-sm text-red-400">{error}</p>
      )}

      <button
        onClick={handleSubmit}
        disabled={!rating || submitting}
        className="mt-3 rounded-full bg-white text-black px-5 py-2.5 text-sm font-medium hover:bg-neutral-200 transition disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? "Submitting..." : "Submit feedback"}
      </button>
    </div>
  );
}
