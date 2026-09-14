-- CreateEnum
CREATE TYPE "Role" AS ENUM ('ADMIN', 'SALES', 'CURATOR', 'PARENT', 'STUDENT');

-- CreateEnum
CREATE TYPE "UserStatus" AS ENUM ('ACTIVE', 'INVITED', 'SUSPENDED');

-- CreateEnum
CREATE TYPE "LeadStatus" AS ENUM ('NEW', 'CONTACTED', 'ASSESSMENT_PAID', 'ASSESSMENT_DONE', 'PROPOSAL_SENT', 'CONTRACT_SENT', 'WON', 'LOST');

-- CreateTable
CREATE TABLE "User" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "phone" TEXT,
    "passwordHash" TEXT,
    "oauthId" TEXT,
    "role" "Role" NOT NULL DEFAULT 'STUDENT',
    "status" "UserStatus" NOT NULL DEFAULT 'INVITED',
    "locale" TEXT NOT NULL DEFAULT 'ru',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "deletedAt" TIMESTAMP(3),

    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Lead" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "contact" TEXT NOT NULL,
    "role" TEXT NOT NULL DEFAULT 'parent',
    "interest" TEXT NOT NULL DEFAULT 'assessment',
    "source" TEXT NOT NULL DEFAULT 'site_form',
    "status" "LeadStatus" NOT NULL DEFAULT 'NEW',
    "consent" BOOLEAN NOT NULL,
    "locale" TEXT NOT NULL DEFAULT 'ru',
    "assignedSalesId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "deletedAt" TIMESTAMP(3),

    CONSTRAINT "Lead_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "groups" (
    "id" SERIAL NOT NULL,
    "name" TEXT NOT NULL,
    "start_date" DATE,
    "lesson_time" TEXT,
    "shift" TEXT NOT NULL DEFAULT 'evening',
    "format" TEXT,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "groups_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "students" (
    "id" SERIAL NOT NULL,
    "group_id" INTEGER NOT NULL,
    "full_name" TEXT NOT NULL,
    "short_name" TEXT,
    "class_school" TEXT,
    "team" TEXT,
    "phone" TEXT,
    "tg_user_id" BIGINT,
    "active" BOOLEAN NOT NULL DEFAULT true,

    CONSTRAINT "students_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "kid_feedback" (
    "id" SERIAL NOT NULL,
    "student_id" INTEGER NOT NULL,
    "group_id" INTEGER NOT NULL,
    "day_index" INTEGER NOT NULL,
    "rating" INTEGER,
    "text" TEXT,
    "source" TEXT NOT NULL DEFAULT 'text',
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "kid_feedback_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "hack_teams" (
    "id" SERIAL NOT NULL,
    "name" TEXT NOT NULL,
    "case_name" TEXT,
    "leader_id" INTEGER NOT NULL,
    "join_code" TEXT NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "hack_teams_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "hack_team_members" (
    "team_id" INTEGER NOT NULL,
    "student_id" INTEGER NOT NULL,
    "joined_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "hack_team_members_pkey" PRIMARY KEY ("team_id","student_id")
);

-- CreateTable
CREATE TABLE "roster" (
    "phone" TEXT NOT NULL,
    "full_name" TEXT NOT NULL,
    "group_id" INTEGER,
    "is_admin" BOOLEAN NOT NULL DEFAULT false,
    "is_mentor" BOOLEAN NOT NULL DEFAULT true,

    CONSTRAINT "roster_pkey" PRIMARY KEY ("phone")
);

-- CreateTable
CREATE TABLE "mentors" (
    "id" SERIAL NOT NULL,
    "tg_user_id" BIGINT NOT NULL,
    "phone" TEXT,
    "full_name" TEXT,
    "is_admin" BOOLEAN NOT NULL DEFAULT false,
    "is_mentor" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "mentors_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "mentor_groups" (
    "mentor_id" INTEGER NOT NULL,
    "group_id" INTEGER NOT NULL,

    CONSTRAINT "mentor_groups_pkey" PRIMARY KEY ("mentor_id","group_id")
);

-- CreateTable
CREATE TABLE "sessions" (
    "id" SERIAL NOT NULL,
    "mentor_id" INTEGER NOT NULL,
    "group_id" INTEGER NOT NULL,
    "day_index" INTEGER NOT NULL,
    "kind" TEXT NOT NULL DEFAULT 'lesson',
    "status" TEXT NOT NULL DEFAULT 'open',
    "started_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finished_at" TIMESTAMPTZ(6),

    CONSTRAINT "sessions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "answers" (
    "id" SERIAL NOT NULL,
    "session_id" INTEGER NOT NULL,
    "group_id" INTEGER NOT NULL,
    "day_index" INTEGER NOT NULL,
    "student_id" INTEGER,
    "question_key" TEXT NOT NULL,
    "question_text" TEXT,
    "maps_to" TEXT,
    "value" TEXT,
    "text" TEXT,
    "source" TEXT NOT NULL DEFAULT 'text',
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "answers_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "characteristics" (
    "id" SERIAL NOT NULL,
    "student_id" INTEGER NOT NULL,
    "payload" JSONB NOT NULL,
    "html_path" TEXT,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "characteristics_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "notifications" (
    "key" TEXT NOT NULL,
    "sent_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "notifications_pkey" PRIMARY KEY ("key")
);

-- CreateTable
CREATE TABLE "invites" (
    "token" TEXT NOT NULL,
    "group_id" INTEGER NOT NULL,
    "student_id" INTEGER,
    "role" TEXT NOT NULL DEFAULT 'mentor',
    "created_by" BIGINT,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "revoked" BOOLEAN NOT NULL DEFAULT false,
    "used_by_tg" BIGINT,
    "used_at" TIMESTAMPTZ(6),

    CONSTRAINT "invites_pkey" PRIMARY KEY ("token")
);

-- CreateTable
CREATE TABLE "workbook_entries" (
    "student_id" INTEGER NOT NULL,
    "field_id" TEXT NOT NULL,
    "value" JSONB NOT NULL,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_by_tg" BIGINT,

    CONSTRAINT "workbook_entries_pkey" PRIMARY KEY ("student_id","field_id")
);

-- CreateTable
CREATE TABLE "workbook_drawings" (
    "student_id" INTEGER NOT NULL,
    "field_id" TEXT NOT NULL,
    "file_path" TEXT NOT NULL,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "workbook_drawings_pkey" PRIMARY KEY ("student_id","field_id")
);

-- CreateIndex
CREATE UNIQUE INDEX "User_email_key" ON "User"("email");

-- CreateIndex
CREATE UNIQUE INDEX "groups_name_key" ON "groups"("name");

-- CreateIndex
CREATE UNIQUE INDEX "students_tg_user_id_key" ON "students"("tg_user_id");

-- CreateIndex
CREATE UNIQUE INDEX "students_group_id_full_name_key" ON "students"("group_id", "full_name");

-- CreateIndex
CREATE INDEX "idx_kid_feedback_group_day" ON "kid_feedback"("group_id", "day_index");

-- CreateIndex
CREATE UNIQUE INDEX "hack_teams_join_code_key" ON "hack_teams"("join_code");

-- CreateIndex
CREATE UNIQUE INDEX "mentors_tg_user_id_key" ON "mentors"("tg_user_id");

-- CreateIndex
CREATE INDEX "idx_sessions_group_day" ON "sessions"("group_id", "day_index", "kind");

-- CreateIndex
CREATE INDEX "idx_answers_student" ON "answers"("student_id");

-- CreateIndex
CREATE INDEX "idx_answers_session" ON "answers"("session_id");

-- CreateIndex
CREATE INDEX "workbook_entries_updated_at_idx" ON "workbook_entries"("updated_at");

-- AddForeignKey
ALTER TABLE "Lead" ADD CONSTRAINT "Lead_assignedSalesId_fkey" FOREIGN KEY ("assignedSalesId") REFERENCES "User"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "students" ADD CONSTRAINT "students_group_id_fkey" FOREIGN KEY ("group_id") REFERENCES "groups"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "kid_feedback" ADD CONSTRAINT "kid_feedback_student_id_fkey" FOREIGN KEY ("student_id") REFERENCES "students"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "kid_feedback" ADD CONSTRAINT "kid_feedback_group_id_fkey" FOREIGN KEY ("group_id") REFERENCES "groups"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "hack_teams" ADD CONSTRAINT "hack_teams_leader_id_fkey" FOREIGN KEY ("leader_id") REFERENCES "students"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "hack_team_members" ADD CONSTRAINT "hack_team_members_team_id_fkey" FOREIGN KEY ("team_id") REFERENCES "hack_teams"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "hack_team_members" ADD CONSTRAINT "hack_team_members_student_id_fkey" FOREIGN KEY ("student_id") REFERENCES "students"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "roster" ADD CONSTRAINT "roster_group_id_fkey" FOREIGN KEY ("group_id") REFERENCES "groups"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "mentor_groups" ADD CONSTRAINT "mentor_groups_mentor_id_fkey" FOREIGN KEY ("mentor_id") REFERENCES "mentors"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "mentor_groups" ADD CONSTRAINT "mentor_groups_group_id_fkey" FOREIGN KEY ("group_id") REFERENCES "groups"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_mentor_id_fkey" FOREIGN KEY ("mentor_id") REFERENCES "mentors"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_group_id_fkey" FOREIGN KEY ("group_id") REFERENCES "groups"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "answers" ADD CONSTRAINT "answers_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "sessions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "answers" ADD CONSTRAINT "answers_student_id_fkey" FOREIGN KEY ("student_id") REFERENCES "students"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "characteristics" ADD CONSTRAINT "characteristics_student_id_fkey" FOREIGN KEY ("student_id") REFERENCES "students"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "invites" ADD CONSTRAINT "invites_group_id_fkey" FOREIGN KEY ("group_id") REFERENCES "groups"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "invites" ADD CONSTRAINT "invites_student_id_fkey" FOREIGN KEY ("student_id") REFERENCES "students"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "workbook_entries" ADD CONSTRAINT "workbook_entries_student_id_fkey" FOREIGN KEY ("student_id") REFERENCES "students"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "workbook_drawings" ADD CONSTRAINT "workbook_drawings_student_id_fkey" FOREIGN KEY ("student_id") REFERENCES "students"("id") ON DELETE CASCADE ON UPDATE CASCADE;
