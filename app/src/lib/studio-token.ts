// HMAC-signed token used to hand an authenticated+paid user off from
// igloo.video to the Flask studio hosted on Fly.io.
//
// Format: base64url(json(payload)).base64url(hmac_sha256(payload_b64))
//
// The Python side in execution/web_app.py verifies with the same secret
// (IGLOO_STUDIO_SECRET) and the same algorithm. Keep these two
// implementations in lockstep — any format change must ship to both.

import "server-only";
import { createHmac, timingSafeEqual } from "node:crypto";

export type StudioTokenPayload = {
  run_id: string;
  user_id: string;
  exp: number; // ms since epoch
};

function getSecret(): string {
  const secret = process.env.IGLOO_STUDIO_SECRET;
  if (!secret) {
    throw new Error("IGLOO_STUDIO_SECRET not set");
  }
  return secret;
}

function b64urlEncode(buf: Buffer): string {
  return buf
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function b64urlDecode(s: string): Buffer {
  const pad = s.length % 4 === 0 ? "" : "=".repeat(4 - (s.length % 4));
  return Buffer.from(s.replace(/-/g, "+").replace(/_/g, "/") + pad, "base64");
}

export function mintStudioToken(payload: StudioTokenPayload): string {
  const secret = getSecret();
  const payloadB64 = b64urlEncode(Buffer.from(JSON.stringify(payload), "utf-8"));
  const sig = createHmac("sha256", secret).update(payloadB64).digest();
  const sigB64 = b64urlEncode(sig);
  return `${payloadB64}.${sigB64}`;
}

export function verifyStudioToken(token: string): StudioTokenPayload | null {
  try {
    const secret = getSecret();
    const [payloadB64, sigB64] = token.split(".");
    if (!payloadB64 || !sigB64) return null;

    const expected = createHmac("sha256", secret).update(payloadB64).digest();
    const given = b64urlDecode(sigB64);
    if (expected.length !== given.length) return null;
    if (!timingSafeEqual(expected, given)) return null;

    const payload = JSON.parse(b64urlDecode(payloadB64).toString("utf-8")) as StudioTokenPayload;
    if (typeof payload.exp !== "number" || Date.now() > payload.exp) return null;
    if (!payload.run_id || !payload.user_id) return null;

    return payload;
  } catch {
    return null;
  }
}
