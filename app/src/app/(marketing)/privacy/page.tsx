import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy — Igloo",
};

export default function PrivacyPage() {
  return (
    <>
      <h1>Privacy Policy</h1>
      <p className="meta">Last updated: 7 April 2026</p>

      <p>This Privacy Policy explains how Igloo (&ldquo;we&rdquo;, &ldquo;us&rdquo;, &ldquo;our&rdquo;) collects, uses, and protects your information when you use our website and services. By using Igloo, you agree to the practices described below.</p>

      <h2>1. Information We Collect</h2>
      <p>We collect only what we need to deliver and improve the service:</p>
      <ul>
        <li><strong>Account information:</strong> name (if provided), email address, and authentication data managed by our identity provider.</li>
        <li><strong>Reel inputs:</strong> the topic, theme, and any text or assets you submit when creating a reel.</li>
        <li><strong>Generated outputs:</strong> the videos, scripts, voiceovers, and intermediates produced by your requests.</li>
        <li><strong>Payment metadata:</strong> transaction identifiers and amounts. We do not store full card numbers, UPI handles, or bank details — those are handled by our payment processor.</li>
        <li><strong>Usage data:</strong> standard logs (IP address, browser type, timestamps) used to diagnose problems and prevent abuse.</li>
      </ul>

      <h2>2. How We Use Your Information</h2>
      <ul>
        <li>To generate, deliver, and store the reels you request.</li>
        <li>To process payments and credit your account.</li>
        <li>To communicate with you about your orders, account, or support requests.</li>
        <li>To improve the service, debug failures, and protect against abuse.</li>
      </ul>

      <h2>3. Third-Party Services</h2>
      <p>Igloo relies on third-party providers to operate. Each handles your data under their own privacy terms:</p>
      <ul>
        <li><strong>Authentication:</strong> Clerk</li>
        <li><strong>Database &amp; file storage:</strong> Supabase</li>
        <li><strong>Compute:</strong> Modal</li>
        <li><strong>Hosting:</strong> Vercel</li>
        <li><strong>Payments:</strong> Razorpay</li>
        <li><strong>AI generation:</strong> Google Gemini, ElevenLabs, Kling AI</li>
      </ul>
      <p>We do not sell your personal information to anyone, and we do not share it with third parties for marketing purposes.</p>

      <h2>4. Data Retention</h2>
      <p>We retain your account, payment records, and generated reels for as long as your account is active and for a reasonable period thereafter for tax and accounting purposes. You may request deletion of your account and associated reels at any time by contacting <a href="mailto:support@igloo.video">support@igloo.video</a>.</p>

      <h2>5. Your Rights</h2>
      <p>You may request access to, correction of, or deletion of your personal data by emailing <a href="mailto:support@igloo.video">support@igloo.video</a>. We will respond within a reasonable timeframe.</p>

      <h2>6. Cookies</h2>
      <p>Igloo uses essential cookies required for authentication and session management. We do not use advertising or third-party tracking cookies.</p>

      <h2>7. Security</h2>
      <p>We use industry-standard measures (HTTPS, hashed passwords via our identity provider, encrypted storage) to protect your information. No system is perfectly secure, but we take reasonable steps to minimize risk.</p>

      <h2>8. Children</h2>
      <p>Igloo is not intended for users under 18. We do not knowingly collect personal information from children.</p>

      <h2>9. Changes to This Policy</h2>
      <p>We may update this policy from time to time. Material changes will be communicated via email or a notice on this page. Continued use of Igloo after changes constitutes acceptance of the updated policy.</p>

      <h2>10. Contact</h2>
      <p>Questions about this policy? Email <a href="mailto:support@igloo.video">support@igloo.video</a>.</p>
    </>
  );
}
