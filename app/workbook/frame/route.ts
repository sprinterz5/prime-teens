import { readFile } from "node:fs/promises";
import path from "node:path";
import { getSession } from "@/lib/auth/session";
import { canReadStudent } from "@/lib/auth/authorize";
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
 * Serves the static platform build of the workbook (public/workbook/app.html)
 * with a small `window.__WB__ = {...}` config script injected right after
 * <body>. Loaded in an <iframe> by /workbook and /mentor/students/[id] so the
 * heavy static HTML stays a build artifact, while auth stays same-origin
 * (this route reads the session cookie itself, and the embedded script's
 * fetch()/EventSource calls to /api/workbook/... inherit the same cookie).
 */
export async function GET(request: Request) {
  const session = await getSession();
  if (!session) return errorPage(401, "Не авторизовано.");

  const url = new URL(request.url);
  let studentId: number;

  if (session.role === "student") {
    if (!session.studentId) return errorPage(400, "У сессии нет studentId.");
    studentId = session.studentId;
  } else {
    const raw = url.searchParams.get("studentId");
    studentId = Number(raw);
    if (!raw || !Number.isInteger(studentId)) return errorPage(400, "Не указан studentId.");
    if (!(await canReadStudent(session, studentId))) return errorPage(403, "Доступ запрещён.");
  }

  // A student whose group has been archived ("Завершить поток") gets the
  // same readonly rendering a mentor sees — inputs disabled, drawings loaded
  // but not editable — plus a "read only" notice (see __WB__.archived below).
  const groupInfo = await getStudentGroupInfo(studentId);
  if (!groupInfo) return errorPage(404, "Студент не найден.");
  const archived = !!groupInfo.archivedAt;
  const mode: "edit" | "readonly" = session.role === "student" && !archived ? "edit" : "readonly";

  let html: string;
  try {
    html = await readFile(APP_HTML_PATH, "utf8");
  } catch {
    return errorPage(500, "Тетрадь не собрана: нет public/workbook/app.html (запустите build_web.py).");
  }

  const config = JSON.stringify({ mode, studentId, apiBase: "/api/workbook", archived });
  const injected = html.replace("<body>", `<body><script>window.__WB__=${config};</script>`);

  return new Response(injected, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "private, no-store"
    }
  });
}
