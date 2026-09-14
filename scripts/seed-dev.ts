/**
 * Idempotent dev-only seed: one test group, one admin, one mentor, three
 * students with obviously-fake data, plus a couple of workbook entries for
 * the first student so /workbook and /mentor have something to show.
 *
 * Run with: pnpm db:seed
 */
import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

// Fake Telegram user ids, well outside any range Telegram actually issues to
// real accounts today, so they can never collide with real data.
const FAKE_TG = {
  admin: BigInt(900000001),
  mentor: BigInt(900000002),
  student1: BigInt(900000011),
  student2: BigInt(900000012),
  student3: BigInt(900000013)
};

function nextMonday(from = new Date()): Date {
  const day = from.getDay(); // 0=Sun..6=Sat
  const daysUntilMonday = ((1 - day + 7) % 7) || 7;
  const d = new Date(Date.UTC(from.getFullYear(), from.getMonth(), from.getDate() + daysUntilMonday));
  return d;
}

async function main() {
  const group = await prisma.group.upsert({
    where: { name: "Тестовая группа" },
    update: {},
    create: {
      name: "Тестовая группа",
      startDate: nextMonday(),
      lessonTime: "10:00",
      shift: "morning",
      format: "online"
    }
  });
  console.log(`Группа: ${group.name} (id=${group.id}), старт ${group.startDate?.toISOString().slice(0, 10)}`);

  const admin = await prisma.mentor.upsert({
    where: { tgUserId: FAKE_TG.admin },
    update: {},
    create: {
      tgUserId: FAKE_TG.admin,
      fullName: "Тест Админов (dev)",
      isAdmin: true,
      isMentor: true
    }
  });
  console.log(`Админ: ${admin.fullName} (id=${admin.id})`);

  const mentor = await prisma.mentor.upsert({
    where: { tgUserId: FAKE_TG.mentor },
    update: {},
    create: {
      tgUserId: FAKE_TG.mentor,
      fullName: "Тест Менторов (dev)",
      isAdmin: false,
      isMentor: true
    }
  });
  console.log(`Ментор: ${mentor.fullName} (id=${mentor.id})`);

  await prisma.mentorGroup.upsert({
    where: { mentorId_groupId: { mentorId: mentor.id, groupId: group.id } },
    update: {},
    create: { mentorId: mentor.id, groupId: group.id }
  });

  const studentDefs = [
    { fullName: "Тест Ученикова Алина (dev)", shortName: "Алина", tgUserId: FAKE_TG.student1 },
    { fullName: "Тест Ученикова Бек (dev)", shortName: "Бек", tgUserId: FAKE_TG.student2 },
    { fullName: "Тест Ученикова Вика (dev)", shortName: "Вика", tgUserId: FAKE_TG.student3 }
  ];

  const students = [];
  for (const def of studentDefs) {
    const student = await prisma.student.upsert({
      where: { groupId_fullName: { groupId: group.id, fullName: def.fullName } },
      update: {},
      create: {
        groupId: group.id,
        fullName: def.fullName,
        shortName: def.shortName,
        tgUserId: def.tgUserId,
        active: true
      }
    });
    students.push(student);
    console.log(`Ученик: ${student.fullName} (id=${student.id})`);
  }

  const [first] = students;
  const sampleEntries: Array<{ fieldId: string; value: unknown }> = [
    { fieldId: "notebook-owner", value: first.fullName },
    { fieldId: "notebook-class", value: "9 класс" },
    { fieldId: "notebook-team", value: "Ракета" }
  ];
  for (const entry of sampleEntries) {
    await prisma.workbookEntry.upsert({
      where: { studentId_fieldId: { studentId: first.id, fieldId: entry.fieldId } },
      update: { value: entry.value as never },
      create: {
        studentId: first.id,
        fieldId: entry.fieldId,
        value: entry.value as never,
        updatedByTg: first.tgUserId
      }
    });
  }
  console.log(`Заполнено ${sampleEntries.length} полей тетради для ${first.fullName}`);
}

main()
  .catch((err) => {
    console.error(err);
    process.exitCode = 1;
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
