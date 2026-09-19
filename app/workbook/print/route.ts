import { readFile } from "node:fs/promises";
import path from "node:path";
import { getSession, verifyPrintToken } from "@/lib/auth/session";
import { getStudentGroupInfo } from "@/lib/workbook/archive";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const APP_HTML_PATH = path.join(process.cwd(), "public", "workbook", "app.html");

function errorPage(status: number, message: string): Response {
  return new Response(
    `<!doctype html><meta charset="utf-8"><body style="font-family:sans-serif;padding:2rem;color:#333">${message}</body>`,
    { status, headers: { "Content-Type": "text/html; charset=utf-8" } }
  );
}

/**
 * Print-only rendering of a single student's workbook, for PDF export
 * (scripts/*.ts drive Playwright/Chromium against this route — see
 * lib/workbook/export-pdf.ts). NOT reachable by a plain session the way
 * /workbook/frame is: this route accepts either
 *   - a live admin session (a human opening it directly to sanity-check), or
 *   - a short-lived ?token=... signed with SESSION_SECRET
 *     (lib/auth/session.ts:encodePrintToken), minted by the export script.
 * Always renders readonly — this is a frozen snapshot, not an editing UI —
 * and sets window.__WB__.print=true so the client hides the top bar/status
 * and lays out at A4 (see PLATFORM_JS/PLATFORM_CSS in
 * workbook/src/build_web.py) even when a real browser (not Chromium's print
 * media emulation) opens this URL directly.
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const raw = url.searchParams.get("studentId");
  const studentId = Number(raw);
  if (!raw || !Number.isInteger(studentId)) return errorPage(400, "Не указан studentId.");

  const token = url.searchParams.get("token");
  let authorized = verifyPrintToken(token, studentId);
  if (!authorized) {
    const session = await getSession();
    authorized = !!session && session.role === "admin";
  }
  if (!authorized) return errorPage(403, "Доступ запрещён.");

  const groupInfo = await getStudentGroupInfo(studentId);
  if (!groupInfo) return errorPage(404, "Студент не найден.");

  let html: string;
  try {
    html = await readFile(APP_HTML_PATH, "utf8");
  } catch {
    return errorPage(500, "Тетрадь не собрана: нет public/workbook/app.html (запустите build_web.py).");
  }

  // The embedded client fetches entries/drawings/stream itself (same code
  // path as /workbook/frame) — those API routes normally authorize by
  // session cookie, which a headless Playwright context driven by the
  // export script never has. Forward the SAME short-lived token so the
  // client can pass it back on those requests too (see PLATFORM_JS: every
  // API URL gets ?token=... appended when WB.token is set) and the three
  // read routes accept it as an alternative to a session (see
  // verifyPrintToken usage in entries/drawings/stream GET handlers). Only
  // set when this request itself was token-authorized — an admin viewing
  // this page with a live session doesn't need it (their cookie already
  // authorizes those requests).
  const config = JSON.stringify({
    mode: "readonly",
    studentId,
    apiBase: "/api/workbook",
    archived: !!groupInfo.archivedAt,
    print: true,
    token: token && verifyPrintToken(token, studentId) ? token : null
  });
  const injected = html.replace("<body>", `<body><script>window.__WB__=${config};</script>`);

  return new Response(injected, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "private, no-store"
    }
  });
}
