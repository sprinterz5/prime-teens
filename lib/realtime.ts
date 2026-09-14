import { Client } from "pg";
import { prisma } from "@/lib/prisma";

// Realtime fan-out for the workbook: every INSERT/UPDATE that should be
// pushed live to a student's mentor (or the student's own other tabs) calls
// notifyWorkbook() below, which does `pg_notify('workbook', json)`. A single
// shared `pg` connection LISTENs on that channel and re-dispatches to
// whichever SSE route handlers are currently subscribed, filtered by
// studentId/groupId. Stashed on globalThis so Next dev's HMR module reloads
// reuse the same LISTEN connection instead of leaking a new one per reload.

export type WorkbookNotification = {
  kind: "entry" | "drawing";
  studentId: number;
  groupId: number;
  fieldId: string;
  value?: unknown;
  updatedAt: string;
};

type Subscriber = (msg: WorkbookNotification) => void;

type ListenerState = {
  client: Client;
  ready: Promise<void>;
  studentSubs: Map<number, Set<Subscriber>>;
  groupSubs: Map<number, Set<Subscriber>>;
};

const globalForRealtime = globalThis as unknown as { __wbListener?: ListenerState };

function createListener(): ListenerState {
  const client = new Client({ connectionString: process.env.DATABASE_URL });
  const studentSubs = new Map<number, Set<Subscriber>>();
  const groupSubs = new Map<number, Set<Subscriber>>();

  const ready: Promise<void> = client
    .connect()
    .then(async () => {
      await client.query("LISTEN workbook");
    })
    .catch((err) => {
      console.error("[realtime] failed to connect/listen:", err);
    });

  client.on("notification", (msg) => {
    if (!msg.payload) return;
    let payload: WorkbookNotification;
    try {
      payload = JSON.parse(msg.payload);
    } catch {
      return;
    }
    studentSubs.get(payload.studentId)?.forEach((fn) => fn(payload));
    groupSubs.get(payload.groupId)?.forEach((fn) => fn(payload));
  });

  client.on("error", (err) => {
    console.error("[realtime] listener connection error:", err);
  });

  return { client, ready, studentSubs, groupSubs };
}

function getListener(): ListenerState {
  if (!globalForRealtime.__wbListener) {
    globalForRealtime.__wbListener = createListener();
  }
  return globalForRealtime.__wbListener;
}

function addSub(map: Map<number, Set<Subscriber>>, id: number, fn: Subscriber) {
  let set = map.get(id);
  if (!set) {
    set = new Set();
    map.set(id, set);
  }
  set.add(fn);
}

function removeSub(map: Map<number, Set<Subscriber>>, id: number, fn: Subscriber) {
  const set = map.get(id);
  if (!set) return;
  set.delete(fn);
  if (set.size === 0) map.delete(id);
}

export async function subscribeStudent(studentId: number, fn: Subscriber): Promise<() => void> {
  const state = getListener();
  await state.ready;
  addSub(state.studentSubs, studentId, fn);
  return () => removeSub(state.studentSubs, studentId, fn);
}

export async function subscribeGroup(groupId: number, fn: Subscriber): Promise<() => void> {
  const state = getListener();
  await state.ready;
  addSub(state.groupSubs, groupId, fn);
  return () => removeSub(state.groupSubs, groupId, fn);
}

/** Publish a change. Uses the app's normal Prisma pool — no dedicated connection needed for NOTIFY. */
export async function notifyWorkbook(payload: WorkbookNotification): Promise<void> {
  await prisma.$executeRaw`SELECT pg_notify('workbook', ${JSON.stringify(payload)})`;
}
