-- AlterTable
ALTER TABLE "groups" ADD COLUMN     "archive_reopened" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN     "archived_at" TIMESTAMPTZ(6),
ADD COLUMN     "ends_at" TIMESTAMPTZ(6);
