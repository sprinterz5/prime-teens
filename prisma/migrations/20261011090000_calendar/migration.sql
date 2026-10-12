-- AlterTable
ALTER TABLE "students" ADD COLUMN     "calendar_token" TEXT;

-- CreateTable
CREATE TABLE "student_deadlines" (
    "id" SERIAL NOT NULL,
    "student_id" INTEGER NOT NULL,
    "title" TEXT NOT NULL,
    "due_at" TIMESTAMPTZ(6) NOT NULL,
    "all_day" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "student_deadlines_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "idx_student_deadlines_student" ON "student_deadlines"("student_id", "due_at");

-- CreateIndex
CREATE UNIQUE INDEX "students_calendar_token_key" ON "students"("calendar_token");

-- AddForeignKey
ALTER TABLE "student_deadlines" ADD CONSTRAINT "student_deadlines_student_id_fkey" FOREIGN KEY ("student_id") REFERENCES "students"("id") ON DELETE CASCADE ON UPDATE CASCADE;

