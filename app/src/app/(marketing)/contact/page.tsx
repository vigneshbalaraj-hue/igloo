import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Contact — Igloo",
};

export default function ContactPage() {
  return (
    <>
      <h1>Contact</h1>
      <p className="meta">We respond within one business day</p>

      <p>The fastest way to reach us is by email. We read every message and respond personally.</p>

      <div className="callout">
        <strong>Email:</strong> <a href="mailto:support@igloo.video">support@igloo.video</a>
      </div>

      <h2>What to write about</h2>
      <ul>
        <li><strong>Order help:</strong> include your order ID and a brief description of the issue.</li>
        <li><strong>Refunds:</strong> see our <a href="/refund">Refund Policy</a> first; most refunds are automatic.</li>
        <li><strong>Account or login problems:</strong> tell us the email you signed up with.</li>
        <li><strong>Privacy or data requests:</strong> see our <a href="/privacy">Privacy Policy</a>.</li>
        <li><strong>Press, partnerships, or feedback:</strong> we&rsquo;d love to hear from you.</li>
      </ul>

      <h2>Response time</h2>
      <p>We respond to all emails within one business day. Beta-period orders are reviewed in waves, so reel delivery may take longer than the email response itself — but we will always confirm receipt and give you a delivery estimate.</p>

      <h2>Operating jurisdiction</h2>
      <p>Igloo operates from India.</p>
    </>
  );
}
