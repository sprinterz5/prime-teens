// Runs once when the Next.js server starts. In production it refuses to boot with
// missing or unsafe configuration instead of failing later on the first login.
export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs" || process.env.NODE_ENV !== "production") return;

  const problems: string[] = [];
  const secret = process.env.SESSION_SECRET ?? "";
  const databaseUrl = process.env.DATABASE_URL ?? "";

  if (secret.length < 32) problems.push("SESSION_SECRET must be set and at least 32 characters (openssl rand -hex 32)");
  if (process.env.DEV_LOGIN === "1") problems.push("DEV_LOGIN=1 must not be set in production");
  if (!databaseUrl) problems.push("DATABASE_URL is not set");
  if (databaseUrl.includes("primeteens_dev_password")) problems.push("DATABASE_URL still uses the dev password");
  if (!process.env.TELEGRAM_KIDS_BOT_TOKEN) problems.push("TELEGRAM_KIDS_BOT_TOKEN is not set");
  if (!process.env.TELEGRAM_MENTOR_BOT_TOKEN) problems.push("TELEGRAM_MENTOR_BOT_TOKEN is not set");

  if (problems.length > 0) {
    throw new Error(`Unsafe production configuration:\n- ${problems.join("\n- ")}`);
  }
}
