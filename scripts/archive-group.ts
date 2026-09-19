/**
 * «Завершить поток» from the command line — sets archivedAt (if not already
 * set), converts the group's drawings to WebP, and exports one PDF per
 * student. Re-runnable: every step is idempotent (see
 * lib/workbook/archive.ts:convertGroupDrawingsToWebp and
 * lib/workbook/export-pdf.ts:exportGroupPdfs — both skip work already done).
 *
 * Usage:
 *   pnpm archive:group <groupId> [--dry-run] [--skip-pdf]
 *
 * --dry-run   prints what would happen (group name, student count, drawings
 *             pending conversion) and makes no changes at all.
 * --skip-pdf  archives + converts drawings but skips the (slow) PDF export —
 *             useful for testing the lock/compression steps quickly.
 *
 * The admin dashboard button (POST /api/admin/groups/[groupId]/archive)
 * covers steps 1-2 (lock + WebP) synchronously; this script is the one place
 * that also does step 3 (PDF), and is what `pnpm archive:pending` (see that
 * script) calls per group under a nightly systemd timer.
 */
import { prisma } from "@/lib/prisma";
import { notifyGroupArchiveChanged } from "@/lib/realtime";
import { convertGroupDrawingsToWebp } from "@/lib/workbook/archive";
import { exportGroupPdfs } from "@/lib/workbook/export-pdf";

function baseUrl(): string {
  return process.env.ARCHIVE_BASE_URL || process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";
}

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

async function main() {
  const args = process.argv.slice(2);
  const positional = args.filter((a) => !a.startsWith("--"));
  const dryRun = args.includes("--dry-run");
  const skipPdf = args.includes("--skip-pdf");

  const groupId = Number(positional[0]);
  if (!Number.isInteger(groupId)) {
    console.error("Использование: pnpm archive:group <groupId> [--dry-run] [--skip-pdf]");
    process.exit(1);
  }

  const group = await prisma.group.findUnique({ where: { id: groupId } });
  if (!group) {
    console.error(`Группа id=${groupId} не найдена — отказ (проверьте id).`);
    process.exit(1);
  }

  const students = await prisma.student.findMany({
    where: { groupId },
    select: { id: true, fullName: true },
    orderBy: { fullName: "asc" }
  });
  const drawingsPending = await prisma.workbookDrawing.count({
    where: { student: { groupId }, filePath: { not: { endsWith: ".webp" } } }
  });

  console.log(`Группа: ${group.name} (id=${group.id})`);
  console.log(`  archivedAt: ${group.archivedAt ? group.archivedAt.toISOString() : "не заперта"}`);
  console.log(`  учеников: ${students.length}`);
  console.log(`  рисунков к конвертации (ещё не .webp): ${drawingsPending}`);

  if (dryRun) {
    console.log("\n--dry-run: изменений не будет.");
    await prisma.$disconnect();
    return;
  }

  if (!group.archivedAt) {
    const archivedAt = new Date();
    await prisma.group.update({ where: { id: groupId }, data: { archivedAt, archiveReopened: false } });
    await notifyGroupArchiveChanged(
      groupId,
      students.map((s) => s.id),
      true,
      archivedAt.toISOString()
    );
    console.log(`\nЗаперто: archivedAt = ${archivedAt.toISOString()}`);
  } else {
    console.log("\nУже заперта — пропускаем блокировку, но всё равно догоняем WebP/PDF.");
  }

  const webp = await convertGroupDrawingsToWebp(groupId);
  console.log(
    `\nWebP: сконвертировано ${webp.converted}, пропущено ${webp.skipped} ` +
      `| было ${fmtBytes(webp.bytesBefore)} -> стало ${fmtBytes(webp.bytesAfter)}` +
      (webp.bytesBefore > 0 ? ` (−${(100 - (webp.bytesAfter / webp.bytesBefore) * 100).toFixed(0)}%)` : "")
  );

  if (skipPdf) {
    console.log("\n--skip-pdf: PDF не экспортируются.");
    await prisma.$disconnect();
    return;
  }

  console.log(`\nЭкспорт PDF (${baseUrl()})...`);
  const pdfs = await exportGroupPdfs(baseUrl(), groupId, students);
  let totalBytes = 0;
  for (const p of pdfs) {
    totalBytes += p.bytes;
    console.log(`  ${p.skipped ? "уже есть" : "создан "} ${p.relPath} (${fmtBytes(p.bytes)})`);
  }
  console.log(`Готово: ${pdfs.length} PDF, суммарно ${fmtBytes(totalBytes)}`);

  await prisma.$disconnect();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
