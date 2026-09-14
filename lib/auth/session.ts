import { createHmac, timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";
import type { NextResponse } from "next/server";

export const SESSION_COOKIE = "wb_session";
const MAX_AGE_SECONDS = 30 * 24 * 60 * 60; // 30 days

export type Role = "student" | "mentor" | "admin";

export type SessionPayload = {
  role: Role;
  tgUserId: string; // BigInt serialized as string (JSON has no bigint)
  studentId?: number;
  mentorId?: number;
  exp: number; // unix seconds
};

function getSecret(): string {
  const secret = process.env.SESSION_SECRET;
  if (!secret) {
    throw new Error("SESSION_SECRET is not set — required to sign/verify session cookies");
  }
  return secret;
}

function base64url(input: Buffer | string): string {
  return Buffer.from(input).toString("base64url");
}

function sign(payloadB64: string): string {
  return createHmac("sha256", getSecret()).update(payloadB64).digest("base64url");
}

export function encodeSession(payload: SessionPayload): string {
  const body = base64url(JSON.stringify(payload));
  const sig = sign(body);
  return `${body}.${sig}`;
}

export function decodeSession(token: string | undefined | null): SessionPayload | null {
  if (!token) return null;
  const dot = token.lastIndexOf(".");
  if (dot < 0) return null;
  const body = token.slice(0, dot);
  const sig = token.slice(dot + 1);
  const expected = sign(body);

  const sigBuf = Buffer.from(sig);
  const expectedBuf = Buffer.from(expected);
  if (sigBuf.length !== expectedBuf.length || !timingSafeEqual(sigBuf, expectedBuf)) {
    return null;
  }

  try {
    const payload = JSON.parse(Buffer.from(body, "base64url").toString("utf8")) as SessionPayload;
    if (typeof payload.exp !== "number" || payload.exp < Math.floor(Date.now() / 1000)) {
      return null;
    }
    return payload;
  } catch {
    return null;
  }
}

/** Read + verify the session cookie for the current request (server components, route handlers). */
export async function getSession(): Promise<SessionPayload | null> {
  const jar = await cookies();
  return decodeSession(jar.get(SESSION_COOKIE)?.value);
}

export function newSessionPayload(input: Omit<SessionPayload, "exp">): SessionPayload {
  return { ...input, exp: Math.floor(Date.now() / 1000) + MAX_AGE_SECONDS };
}

export const SESSION_MAX_AGE_SECONDS = MAX_AGE_SECONDS;

export function applySessionCookie(response: NextResponse, payload: SessionPayload): void {
  response.cookies.set(SESSION_COOKIE, encodeSession(payload), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: MAX_AGE_SECONDS
  });
}

export function clearSessionCookie(response: NextResponse): void {
  response.cookies.set(SESSION_COOKIE, "", { path: "/", maxAge: 0 });
}
