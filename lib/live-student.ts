import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/auth/session";

/** The logged-in student with their group, or null for anyone else. */
export async function currentStudent() {
  const session = await getSession();
  if (session?.role !== "student" || !session.studentId) return null;
  return prisma.student.findUnique({ where: { id: session.studentId }, select: { id: true, groupId: true } });
}
