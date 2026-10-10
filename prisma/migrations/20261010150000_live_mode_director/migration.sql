-- AlterTable
ALTER TABLE "mentors" ADD COLUMN     "is_director" BOOLEAN NOT NULL DEFAULT false;

-- AlterTable
ALTER TABLE "roster" ADD COLUMN     "is_director" BOOLEAN NOT NULL DEFAULT false;

-- CreateTable
CREATE TABLE "live_activities" (
    "id" SERIAL NOT NULL,
    "title" TEXT NOT NULL,
    "day_index" INTEGER,
    "created_by" INTEGER,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "archived_at" TIMESTAMPTZ(6),

    CONSTRAINT "live_activities_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "live_questions" (
    "id" SERIAL NOT NULL,
    "activity_id" INTEGER NOT NULL,
    "position" INTEGER NOT NULL,
    "kind" TEXT NOT NULL,
    "prompt" TEXT NOT NULL,
    "options" JSONB NOT NULL DEFAULT '[]',
    "correct_index" INTEGER,
    "time_limit_sec" INTEGER,

    CONSTRAINT "live_questions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "live_sessions" (
    "id" SERIAL NOT NULL,
    "activity_id" INTEGER,
    "group_id" INTEGER NOT NULL,
    "started_by" INTEGER,
    "title" TEXT NOT NULL,
    "questions" JSONB NOT NULL,
    "current_index" INTEGER NOT NULL DEFAULT -1,
    "phase" TEXT NOT NULL DEFAULT 'lobby',
    "opened_at" TIMESTAMPTZ(6),
    "started_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finished_at" TIMESTAMPTZ(6),

    CONSTRAINT "live_sessions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "live_answers" (
    "session_id" INTEGER NOT NULL,
    "question_index" INTEGER NOT NULL,
    "student_id" INTEGER NOT NULL,
    "value" JSONB NOT NULL,
    "correct" BOOLEAN,
    "answered_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "live_answers_pkey" PRIMARY KEY ("session_id","question_index","student_id")
);

-- CreateIndex
CREATE INDEX "idx_live_questions_activity" ON "live_questions"("activity_id", "position");

-- CreateIndex
CREATE INDEX "idx_live_sessions_group" ON "live_sessions"("group_id", "finished_at");

-- AddForeignKey
ALTER TABLE "live_activities" ADD CONSTRAINT "live_activities_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "mentors"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "live_questions" ADD CONSTRAINT "live_questions_activity_id_fkey" FOREIGN KEY ("activity_id") REFERENCES "live_activities"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "live_sessions" ADD CONSTRAINT "live_sessions_activity_id_fkey" FOREIGN KEY ("activity_id") REFERENCES "live_activities"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "live_sessions" ADD CONSTRAINT "live_sessions_group_id_fkey" FOREIGN KEY ("group_id") REFERENCES "groups"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "live_sessions" ADD CONSTRAINT "live_sessions_started_by_fkey" FOREIGN KEY ("started_by") REFERENCES "mentors"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "live_answers" ADD CONSTRAINT "live_answers_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "live_sessions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "live_answers" ADD CONSTRAINT "live_answers_student_id_fkey" FOREIGN KEY ("student_id") REFERENCES "students"("id") ON DELETE CASCADE ON UPDATE CASCADE;

