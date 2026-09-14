// Dev only: link the first ADMIN_IDS Telegram account from bot/.env to the
// seeded test student and the seeded test admin, so the same person can open
// the workbook as a student (kids bot Mini App) and the dashboard as an admin
// (mentor bot Mini App). The admin also becomes a mentor of the seeded test
// group, so the mentor bot shows that group. Never prints the id.
//
// Usage: pnpm tsx scripts/link-dev-telegram.ts [--phone 8777...]
//   --phone  the tester's Telegram phone; stored on the mentor and in the
//            roster so phone-based lookups in the bot also resolve to them.
import { readFileSync } from "node:fs";
import path from "node:path";
import { PrismaClient } from "@prisma/client";

if (process.env.NODE_ENV === "production") {
  throw new Error("link-dev-telegram is a dev-only script");
}

const envText = readFileSync(path.join(__dirname, "..", "bot", ".env"), "utf8");
const raw = envText.match(/^ADMIN_IDS=(.*)$/m)?.[1] ?? "";
const firstId = raw.split(/[,\s]+/).find((s) => /^\d+$/.test(s));
if (!firstId) throw new Error("ADMIN_IDS in bot/.env has no numeric Telegram id");
const tgUserId = BigInt(firstId);

// Same normalisation as bot/app/db.py norm_phone: digits only, 8XXXXXXXXXX -> 7XXXXXXXXXX.
function normPhone(input: string): string {
  let digits = input.replace(/\D/g, "");
  if (digits.length === 11 && digits.startsWith("8")) digits = `7${digits.slice(1)}`;
  if (digits.length === 10) digits = `7${digits}`;
  return digits;
}

const phoneArgIndex = process.argv.indexOf("--phone");
const phone = phoneArgIndex > -1 ? normPhone(process.argv[phoneArgIndex + 1] ?? "") : null;

const prisma = new PrismaClient();

async function main() {
  const student = await prisma.student.findFirst({
    where: { fullName: { contains: "(dev)" } },
    orderBy: { id: "asc" }
  });
  const admin = await prisma.mentor.findFirst({
    where: { isAdmin: true, fullName: { contains: "(dev)" } },
    orderBy: { id: "asc" }
  });
  if (!student || !admin) throw new Error("Seeded dev student/admin not found — run pnpm db:seed first");

  // Free the id if another row already holds it (both columns are unique).
  await prisma.student.updateMany({ where: { tgUserId, NOT: { id: student.id } }, data: { tgUserId: null } });
  await prisma.student.update({ where: { id: student.id }, data: { tgUserId } });
  await prisma.mentor.update({
    where: { id: admin.id },
    data: { tgUserId, isMentor: true, ...(phone ? { phone } : {}) }
  });
  await prisma.mentorGroup.upsert({
    where: { mentorId_groupId: { mentorId: admin.id, groupId: student.groupId } },
    create: { mentorId: admin.id, groupId: student.groupId },
    update: {}
  });
  if (phone) {
    await prisma.roster.upsert({
      where: { phone },
      create: { phone, fullName: admin.fullName ?? "Тестер (dev)", groupId: student.groupId, isAdmin: true, isMentor: true },
      update: { groupId: student.groupId, isAdmin: true, isMentor: true }
    });
  }

  const group = await prisma.group.findUnique({ where: { id: student.groupId } });
  console.log(
    `linked Telegram account -> student "${student.fullName}" and admin+mentor "${admin.fullName}" ` +
      `of group "${group?.name}"${phone ? " (phone set, roster updated)" : ""}`
  );
}

main().finally(() => prisma.$disconnect());
