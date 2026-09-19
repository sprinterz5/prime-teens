import { createHmac, timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";
import type { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

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

const MIN_PROD_SECRET_LENGTH = 32;

function getSecret(): string {
  const secret = process.env.SESSION_SECRET;
  if (!secret) {
    throw new Error("SESSION_SECRET is not set — required to sign/verify session cookies");
  }
  if (process.env.NODE_ENV === "production" && secret.length < MIN_PROD_SECRET_LENGTH) {
    throw new Error(`SESSION_SECRET must be at least ${MIN_PROD_SECRET_LENGTH} characters in production`);
  }
  return secret;
}

function devLoginEnabled(): boolean {
  return process.env.NODE_ENV !== "production" && process.env.DEV_LOGIN === "1";
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

/**
 * Read + verify the session cookie for the current request (server components, route handlers).
 * The cookie only proves who logged in; the account is re-checked against the database on every
 * request so that unlinking a Telegram account, deactivating a student or changing a mentor's
 * admin flag takes effect immediately instead of after the cookie expires.
 */
export async function getSession(): Promise<SessionPayload | null> {
  const jar = await cookies();
  const payload = decodeSession(jar.get(SESSION_COOKIE)?.value);
  if (!payload) return null;
  return refreshFromDatabase(payload);
}

async function refreshFromDatabase(payload: SessionPayload): Promise<SessionPayload | null> {
  // Sessions minted by /dev/login may carry a placeholder tg id; they are never valid in production.
  const isTelegramId = /^\d+$/.test(payload.tgUserId);
  if (!isTelegramId && !devLoginEnabled()) return null;

  if (payload.role === "student") {
    if (!payload.studentId) return null;
    const student = await prisma.student.findUnique({
      where: { id: payload.studentId },
      select: { tgUserId: true, active: true }
    });
    if (!student || !student.active) return null;
    if (isTelegramId && String(student.tgUserId) !== payload.tgUserId) return null;
    return payload;
  }

  if (!payload.mentorId) return null;
  const mentor = await prisma.mentor.findUnique({
    where: { id: payload.mentorId },
    select: { tgUserId: true, isAdmin: true }
  });
  if (!mentor) return null;
  if (isTelegramId && String(mentor.tgUserId) !== payload.tgUserId) return null;
  return { ...payload, role: mentor.isAdmin ? "admin" : "mentor" };
}

// Short-lived, studentId-bound tokens for /workbook/print — the offline
// archive-export script (scripts/archive-group.ts) can't hold a browser
// session cookie, so it mints one of these and passes it as ?token=... The
// print route accepts either this token OR a live admin session. Same HMAC
// machinery as the session cookie above, just a smaller payload and a much
// shorter TTL (minutes, not days).
export type PrintTokenPayload = { studentId: number; exp: number };

export function encodePrintToken(studentId: number, ttlSeconds = 300): string {
  const body = base64url(JSON.stringify({ studentId, exp: Math.floor(Date.now() / 1000) + ttlSeconds }));
  return `${body}.${sign(body)}`;
}

/** Verifies signature, expiry, AND that the token was minted for this exact studentId. */
export function verifyPrintToken(token: string | undefined | null, studentId: number): boolean {
  if (!token) return false;
  const dot = token.lastIndexOf(".");
  if (dot < 0) return false;
  const body = token.slice(0, dot);
  const sig = token.slice(dot + 1);
  const expected = sign(body);

  const sigBuf = Buffer.from(sig);
  const expectedBuf = Buffer.from(expected);
  if (sigBuf.length !== expectedBuf.length || !timingSafeEqual(sigBuf, expectedBuf)) return false;

  try {
    const payload = JSON.parse(Buffer.from(body, "base64url").toString("utf8")) as PrintTokenPayload;
    if (typeof payload.exp !== "number" || payload.exp < Math.floor(Date.now() / 1000)) return false;
    return payload.studentId === studentId;
  } catch {
    return false;
  }
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
  response.cookies.set(SESSION_COOKIE, "", {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 0
  });
}
