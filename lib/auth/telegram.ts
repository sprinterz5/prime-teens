import { createHmac, timingSafeEqual } from "node:crypto";

const MAX_AUTH_AGE_SECONDS = 24 * 60 * 60; // Telegram's own recommended freshness window

export type TelegramUser = {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string;
};

export type VerifiedInitData = {
  user: TelegramUser;
  authDate: number;
};

/**
 * Verifies Telegram Mini App `initData` per the WebApp spec:
 * https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
 *
 * secret_key = HMAC_SHA256(key="WebAppData", data=botToken)
 * expected   = HMAC_SHA256(key=secret_key, data=dataCheckString)  (hex)
 * dataCheckString = all fields except `hash`, "key=value" sorted by key, joined with "\n"
 */
export function verifyTelegramInitData(
  initData: string,
  botToken: string
): { ok: true; result: VerifiedInitData } | { ok: false; error: string } {
  if (!botToken) return { ok: false, error: "empty bot token" };

  let params: URLSearchParams;
  try {
    params = new URLSearchParams(initData);
  } catch {
    return { ok: false, error: "malformed initData" };
  }

  const hash = params.get("hash");
  if (!hash) return { ok: false, error: "missing hash" };

  const pairs: string[] = [];
  params.forEach((value, key) => {
    if (key === "hash") return;
    pairs.push(`${key}=${value}`);
  });
  pairs.sort();
  const dataCheckString = pairs.join("\n");

  const secretKey = createHmac("sha256", "WebAppData").update(botToken).digest();
  const expectedHash = createHmac("sha256", secretKey).update(dataCheckString).digest("hex");

  const a = Buffer.from(hash, "hex");
  const b = Buffer.from(expectedHash, "hex");
  if (a.length !== b.length || !timingSafeEqual(a, b)) {
    return { ok: false, error: "hash mismatch" };
  }

  const authDateRaw = params.get("auth_date");
  const authDate = authDateRaw ? Number(authDateRaw) : NaN;
  if (!Number.isFinite(authDate)) return { ok: false, error: "missing/invalid auth_date" };
  const now = Math.floor(Date.now() / 1000);
  if (now - authDate > MAX_AUTH_AGE_SECONDS) {
    return { ok: false, error: "auth_date too old" };
  }

  const userRaw = params.get("user");
  if (!userRaw) return { ok: false, error: "missing user" };
  let user: TelegramUser;
  try {
    user = JSON.parse(userRaw);
  } catch {
    return { ok: false, error: "malformed user field" };
  }
  if (typeof user.id !== "number") return { ok: false, error: "user.id missing" };

  return { ok: true, result: { user, authDate } };
}
