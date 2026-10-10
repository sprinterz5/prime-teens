import { NextResponse } from "next/server";
import { forbidden } from "@/lib/auth/authorize";
import { currentStudent } from "@/lib/live-student";
import { studentState } from "@/lib/live-state";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** The live session running in the student's group, as that student may see it. */
export async function GET() {
  const student = await currentStudent();
  if (!student) return forbidden();
  return NextResponse.json(await studentState(student.id, student.groupId));
}
