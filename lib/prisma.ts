import { PrismaClient } from "@prisma/client";

// Standard Next.js dev-HMR-safe singleton: without this, every module reload
// during `next dev` would open a fresh pool of Postgres connections.
const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

export const prisma = globalForPrisma.prisma ?? new PrismaClient();

if (process.env.NODE_ENV !== "production") {
  globalForPrisma.prisma = prisma;
}
