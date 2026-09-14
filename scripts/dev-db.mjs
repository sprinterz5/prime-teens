// Local dev Postgres, used when Docker isn't available (see docker-compose.yml
// for the normal path). Same user/password/db/port so DATABASE_URL in .env
// doesn't need to change either way.
//
// Usage: node scripts/dev-db.mjs   (or `pnpm db:dev`)
// Stop with Ctrl+C (SIGINT/SIGTERM) — data persists in .dev-db/ between runs.
import EmbeddedPostgres from "embedded-postgres";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dataDir = path.join(__dirname, "..", ".dev-db");

const USER = "primeteens";
const PASSWORD = "primeteens_dev_password";
const DATABASE = "primeteens";
const PORT = 5432;

const pg = new EmbeddedPostgres({
  databaseDir: dataDir,
  user: USER,
  password: PASSWORD,
  port: PORT,
  persistent: true,
  authMethod: "password",
  // Without this initdb inherits the Windows ANSI code page (WIN1251), which
  // stores Cyrillic but rejects emoji — and Telegram messages and workbook
  // answers routinely contain emoji. Match docker-compose's UTF8 default.
  initdbFlags: ["--encoding=UTF8", "--locale=C"],
});

async function main() {
  console.log(`[dev-db] data dir: ${dataDir}`);
  await pg.initialise();
  console.log("[dev-db] cluster initialised (or already existed)");

  await pg.start();
  console.log(`[dev-db] postgres listening on 127.0.0.1:${PORT}`);

  try {
    await pg.createDatabase(DATABASE);
    console.log(`[dev-db] database "${DATABASE}" created`);
  } catch (err) {
    // Already exists on subsequent runs — fine.
    console.log(`[dev-db] database "${DATABASE}" already exists`);
  }

  console.log(
    `[dev-db] ready. DATABASE_URL=postgresql://${USER}:${PASSWORD}@localhost:${PORT}/${DATABASE}?schema=public`
  );
  console.log("[dev-db] press Ctrl+C to stop");
}

let stopping = false;
async function shutdown(signal) {
  if (stopping) return;
  stopping = true;
  console.log(`[dev-db] received ${signal}, stopping postgres...`);
  try {
    await pg.stop();
    console.log("[dev-db] stopped cleanly");
  } catch (err) {
    console.error("[dev-db] error while stopping:", err);
  }
  process.exit(0);
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));

main().catch((err) => {
  console.error("[dev-db] failed to start:", err);
  process.exit(1);
});
