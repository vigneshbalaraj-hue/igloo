// Admin auth helper.
//
// Identity model: a Clerk user is "admin" iff their publicMetadata
// has { role: "admin" }. Set this in the Clerk dashboard:
//   Users → pick user → Metadata tab → Public metadata →
//     { "role": "admin" }
//
// Clerk does not include publicMetadata in session claims by default.
// You must add a custom session token in:
//   Clerk dashboard → Sessions → Customize session token →
//     { "metadata": "{{user.public_metadata}}" }
//
// After that, sessionClaims.metadata.role is available server-side.

import "server-only";
import { auth } from "@clerk/nextjs/server";

type SessionMetadata = { role?: string };

export async function requireAdmin(): Promise<{ userId: string }> {
  const { userId, sessionClaims } = await auth();
  if (!userId) {
    throw new AdminAuthError("unauthorized", 401);
  }
  const metadata = (sessionClaims?.metadata as SessionMetadata | undefined) ?? {};
  if (metadata.role !== "admin") {
    throw new AdminAuthError("forbidden", 403);
  }
  return { userId };
}

export async function isAdmin(): Promise<boolean> {
  try {
    await requireAdmin();
    return true;
  } catch {
    return false;
  }
}

export class AdminAuthError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}
