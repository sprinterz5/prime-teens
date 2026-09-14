/**
 * Unit-style test for lib/auth/telegram.ts's verifyTelegramInitData: builds a
 * fake bot token and a self-signed Telegram Mini App initData payload (valid
 * and deliberately-broken variants) and checks the verifier accepts/rejects
 * each as expected. No network, no real Telegram credentials.
 *
 * Run with: pnpm exec tsx scripts/test-telegram-initdata.ts
 */
import { createHmac } from "node:crypto";
import { verifyTelegramInitData } from "../lib/auth/telegram";

const FAKE_BOT_TOKEN = "123456:FAKE-TEST-TOKEN-not-a-real-secret";

function buildInitData(fields: Record<string, string>, botToken: string): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(fields)) params.set(k, v);
  const pairs: string[] = [];
  params.forEach((value, key) => pairs.push(`${key}=${value}`));
  pairs.sort();
  const dataCheckString = pairs.join("\n");
  const secretKey = createHmac("sha256", "WebAppData").update(botToken).digest();
  const hash = createHmac("sha256", secretKey).update(dataCheckString).digest("hex");
  params.set("hash", hash);
  return params.toString();
}

let failures = 0;
function ok(cond: boolean, label: string, extra?: string) {
  if (cond) {
    console.log(`PASS  ${label}`);
  } else {
    failures++;
    console.log(`FAIL  ${label}${extra ? " -- " + extra : ""}`);
  }
}

const now = Math.floor(Date.now() / 1000);
const validFields = {
  auth_date: String(now),
  user: JSON.stringify({ id: 555444333, first_name: "Тест" })
};

const validInitData = buildInitData(validFields, FAKE_BOT_TOKEN);
const r1 = verifyTelegramInitData(validInitData, FAKE_BOT_TOKEN);
ok(r1.ok === true, "valid initData verifies", JSON.stringify(r1));
ok(r1.ok && r1.result.user.id === 555444333, "verified user id matches");

const wrongToken = "999999:another-token-entirely";
const tamperedInitData = buildInitData(validFields, wrongToken);
const r2 = verifyTelegramInitData(tamperedInitData, FAKE_BOT_TOKEN);
ok(r2.ok === false && r2.error === "hash mismatch", "wrong-token-signed initData rejected", JSON.stringify(r2));

const staleFields = {
  auth_date: String(now - 25 * 60 * 60),
  user: JSON.stringify({ id: 555444333, first_name: "Тест" })
};
const staleInitData = buildInitData(staleFields, FAKE_BOT_TOKEN);
const r3 = verifyTelegramInitData(staleInitData, FAKE_BOT_TOKEN);
ok(r3.ok === false && r3.error === "auth_date too old", "stale auth_date (25h) rejected", JSON.stringify(r3));

const r4 = verifyTelegramInitData(`auth_date=${now}&user=%7B%7D`, FAKE_BOT_TOKEN);
ok(r4.ok === false, "missing hash rejected", JSON.stringify(r4));

const flipped = validInitData.replace(/hash=([0-9a-f])/, (_m, c: string) => `hash=${c === "0" ? "1" : "0"}`);
const r5 = verifyTelegramInitData(flipped, FAKE_BOT_TOKEN);
ok(r5.ok === false, "flipped hash character rejected", JSON.stringify(r5));

console.log(`\n${failures === 0 ? "ALL PASS" : failures + " FAILURE(S)"}`);
process.exitCode = failures === 0 ? 0 : 1;
