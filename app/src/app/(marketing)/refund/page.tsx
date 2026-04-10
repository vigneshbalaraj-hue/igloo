import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Refund Policy — Igloo",
};

export default function RefundPage() {
  return (
    <>
      <h1>Refund Policy</h1>
      <p className="meta">Last updated: 7 April 2026</p>

      <div className="callout">
        <strong>Short version:</strong> If your reel is not delivered, fails our quality check, or we reject your request for any reason, you receive a <strong>100% refund within 24 hours</strong>. No forms, no questions.
      </div>

      <h2>1. When You Get a Full Refund</h2>
      <ul>
        <li>The reel fails to generate due to a technical error on our end.</li>
        <li>We reject your reel during our internal quality review (e.g., visual artifacts, lip-sync failure, audio defects).</li>
        <li>We decline your topic for content-policy reasons (see our <a href="/terms">Terms of Service</a>).</li>
        <li>The reel is not delivered to your account within 48 hours of your order.</li>
      </ul>
      <p>In all of these cases, the refund is automatic. You will receive a confirmation email and the funds will be returned to your original payment method within 5–7 business days, depending on your bank.</p>

      <h2>2. When Refunds Are Not Issued</h2>
      <ul>
        <li>The reel was delivered, met our quality bar, and matched the topic you submitted.</li>
        <li>You changed your mind after the reel was generated and delivered.</li>
        <li>You used the reel and later decided you no longer wanted it.</li>
        <li>You requested a topic that violates our acceptable use policy after we already declined it (no double-charging — declined orders are refunded fully the first time).</li>
      </ul>
      <p>Because each reel costs us real compute and AI inference, we cannot offer refunds on delivered work that meets the agreed specification. We make this trade-off explicit so you know what you&rsquo;re buying.</p>

      <h2>3. How to Request a Refund</h2>
      <p>Most refunds happen automatically. If you believe you are owed a refund and have not received it, email <a href="mailto:support@igloo.video">support@igloo.video</a> with your order ID and a brief description. We respond within one business day.</p>

      <h2>4. Chargebacks</h2>
      <p>If you have a problem with an order, please contact us first — we almost always resolve refunds faster than a bank chargeback. Filing a chargeback without first contacting us may result in account suspension.</p>

      <h2>5. Beta-Period Note</h2>
      <p>Igloo is in early beta. We hold every reel to a high quality bar before delivery, but if anything ever feels off about your order, write to us and we will make it right.</p>

      <h2>6. Contact</h2>
      <p>Refund questions: <a href="mailto:support@igloo.video">support@igloo.video</a>.</p>
    </>
  );
}
