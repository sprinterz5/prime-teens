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
  kind: "entry" | "drawing" | "archive_changed";
  studentId: number;
  groupId: number;
  // "archive_changed" broadcasts don't apply to one field, so fieldId is
  // optional for that kind (present for "entry"/"drawing").
  fieldId?: string;
  value?: unknown;
  // "archive_changed" only: true if the group just got locked, false if unlocked.
  archived?: boolean;
  updatedAt: string;
};

// Live mode (lib/live.ts) shares the same LISTEN connection on a second
// channel, "live": every state change or new answer in a group's session.
export type LiveNotification = {
  kind: "state" | "answer";
  sessionId: number;
  groupId: number;
};

type Subscriber = (msg: WorkbookNotification) => void;
type LiveSubscriber = (msg: LiveNotification) => void;

type ListenerState = {
  client: Client;
  ready: Promise<void>;
  studentSubs: Map<number, Set<Subscriber>>;
  groupSubs: Map<number, Set<Subscriber>>;
  liveSubs: Map<number, Set<LiveSubscriber>>;
};

const globalForRealtime = globalThis as unknown as { __wbListener?: ListenerState };

function createListener(): ListenerState {
  const client = new Client({ connectionString: process.env.DATABASE_URL });
  const studentSubs = new Map<number, Set<Subscriber>>();
  const groupSubs = new Map<number, Set<Subscriber>>();
  const liveSubs = new Map<number, Set<LiveSubscriber>>();

  const ready: Promise<void> = client
    .connect()
    .then(async () => {
      await client.query("LISTEN workbook");
      await client.query("LISTEN live");
    })
    .catch((err) => {
      console.error("[realtime] failed to connect/listen:", err);
    });

  client.on("notification", (msg) => {
    if (!msg.payload) return;
    if (msg.channel === "live") {
      let live: LiveNotification;
      try {
        live = JSON.parse(msg.payload);
      } catch {
        return;
      }
      liveSubs.get(live.groupId)?.forEach((fn) => fn(live));
      return;
    }
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

  return { client, ready, studentSubs, groupSubs, liveSubs };
}

function getListener(): ListenerState {
  // A listener created before live mode existed (dev HMR) has no liveSubs — replace it.
  if (globalForRealtime.__wbListener && !globalForRealtime.__wbListener.liveSubs) {
    globalForRealtime.__wbListener.client.end().catch(() => {});
    globalForRealtime.__wbListener = undefined;
  }
  if (!globalForRealtime.__wbListener) {
    globalForRealtime.__wbListener = createListener();
  }
  return globalForRealtime.__wbListener;
}

function addSub<T>(map: Map<number, Set<T>>, id: number, fn: T) {
  let set = map.get(id);
  if (!set) {
    set = new Set();
    map.set(id, set);
  }
  set.add(fn);
}

function removeSub<T>(map: Map<number, Set<T>>, id: number, fn: T) {
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

/**
 * Broadcasts an archive lock/unlock to every student in a group: each
 * student's own /stream (open in "edit" mode while they were still writing)
 * is only subscribed by studentId, so a single groupId-keyed notification
 * wouldn't reach it — we notify once per student instead. The mentor
 * dashboard's per-group stream picks up every one of these too (it's
 * subscribed by groupId), which is fine — it just refetches once per event.
 */
export async function notifyGroupArchiveChanged(
  groupId: number,
  studentIds: number[],
  archived: boolean,
  updatedAt: string
): Promise<void> {
  for (const studentId of studentIds) {
    await notifyWorkbook({ kind: "archive_changed", studentId, groupId, archived, updatedAt });
  }
}

export async function subscribeLiveGroup(groupId: number, fn: LiveSubscriber): Promise<() => void> {
  const state = getListener();
  await state.ready;
  addSub(state.liveSubs, groupId, fn);
  return () => removeSub(state.liveSubs, groupId, fn);
}

export async function notifyLive(payload: LiveNotification): Promise<void> {
  await prisma.$executeRaw`SELECT pg_notify('live', ${JSON.stringify(payload)})`;
}
