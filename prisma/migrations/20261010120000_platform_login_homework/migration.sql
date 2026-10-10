-- CreateTable
CREATE TABLE "login_codes" (
    "token_hash" TEXT NOT NULL,
    "code" TEXT NOT NULL,
    "role" TEXT NOT NULL,
    "student_id" INTEGER,
    "mentor_id" INTEGER,
    "tg_user_id" BIGINT NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expires_at" TIMESTAMPTZ(6) NOT NULL,
    "used_at" TIMESTAMPTZ(6),

    CONSTRAINT "login_codes_pkey" PRIMARY KEY ("token_hash")
);

-- CreateTable
CREATE TABLE "homework" (
    "student_id" INTEGER NOT NULL,
    "day_index" INTEGER NOT NULL,
    "text" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'submitted',
    "mentor_comment" TEXT,
    "submitted_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "reviewed_at" TIMESTAMPTZ(6),
    "reviewed_by" INTEGER,
    "notified_at" TIMESTAMPTZ(6),

    CONSTRAINT "homework_pkey" PRIMARY KEY ("student_id","day_index")
);

-- CreateIndex
CREATE INDEX "idx_login_codes_code" ON "login_codes"("code");

-- CreateIndex
CREATE INDEX "idx_homework_status" ON "homework"("status");

-- AddForeignKey
ALTER TABLE "login_codes" ADD CONSTRAINT "login_codes_student_id_fkey" FOREIGN KEY ("student_id") REFERENCES "students"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "login_codes" ADD CONSTRAINT "login_codes_mentor_id_fkey" FOREIGN KEY ("mentor_id") REFERENCES "mentors"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "homework" ADD CONSTRAINT "homework_student_id_fkey" FOREIGN KEY ("student_id") REFERENCES "students"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "homework" ADD CONSTRAINT "homework_reviewed_by_fkey" FOREIGN KEY ("reviewed_by") REFERENCES "mentors"("id") ON DELETE SET NULL ON UPDATE CASCADE;

