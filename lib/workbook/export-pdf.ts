import { existsSync, statSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";
import { encodePrintToken } from "@/lib/auth/session";
import { groupArchiveDir, studentPdfRelPath } from "@/lib/workbook/archive";

// Playwright must wait for the print page's own async loads (entries fetch +
// every canvas image) before printing — see window.__WB_READY__, set by
// PLATFORM_JS in workbook/src/build_web.py once both are done.
const READY_TIMEOUT_MS = 20_000;
const NAV_TIMEOUT_MS = 30_000;
// A4 at 96dpi-ish width so the workbook's own "fill available width" JS
// (see PLATFORM_JS scale()) doesn't matter — print mode forces zoom:1 anyway
// (see .wb-print-mode in build_web.py), this just needs to be wide enough
// that the mobile (<768px) media query doesn't kick in.
const PRINT_VIEWPORT = { width: 1240, height: 1754 };

export type PdfExportResult = {
  studentId: number;
  fullName: string;
  relPath: string;
  bytes: number;
  skipped: boolean;
};

export type StudentForExport = { id: number; fullName: string };

/**
 * Renders one PDF per student via /workbook/print (see
 * app/workbook/print/route.ts), using a short-lived signed token instead of
 * a session cookie — this runs standalone (script), not inside a logged-in
 * browser. Skips a student whose PDF already exists unless `force` is set,
 * so `pnpm archive:pending` re-running later is cheap.
 */
export async function exportGroupPdfs(
  baseUrl: string,
  groupId: number,
  students: StudentForExport[],
  opts: { force?: boolean } = {}
): Promise<PdfExportResult[]> {
  if (students.length === 0) return [];

  const dirAbs = path.join(process.cwd(), groupArchiveDir(groupId));
  await mkdir(dirAbs, { recursive: true });

  const browser = await chromium.launch();
  const results: PdfExportResult[] = [];
  try {
    const page = await browser.newPage({ viewport: PRINT_VIEWPORT });
    for (const student of students) {
      const rel = studentPdfRelPath(groupId, student.id, student.fullName);
      const abs = path.join(process.cwd(), rel);

      if (!opts.force && existsSync(abs)) {
        results.push({ studentId: student.id, fullName: student.fullName, relPath: rel, bytes: statSync(abs).size, skipped: true });
        continue;
      }

      const token = encodePrintToken(student.id);
      const url = `${baseUrl}/workbook/print?studentId=${student.id}&token=${encodeURIComponent(token)}`;
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: NAV_TIMEOUT_MS });
      await page.waitForFunction("window.__WB_READY__ === true", null, { timeout: READY_TIMEOUT_MS });
      await page.pdf({ path: abs, format: "A4", printBackground: true });

      results.push({ studentId: student.id, fullName: student.fullName, relPath: rel, bytes: statSync(abs).size, skipped: false });
    }
  } finally {
    await browser.close();
  }
  return results;
}
