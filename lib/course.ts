import { readFileSync } from "node:fs";
import path from "node:path";
import { parse } from "yaml";

// Программа курса — тот же bot/config/course.yaml, по которому боты шлют
// напоминания: дни, их задания и домашка. Даты занятий считаются так же,
// как в bot/app/db.py:group_lesson_window — держите правила в синхроне.

/** Часовой пояс курса — TZ ботов по умолчанию (bot/.env.example). */
export const COURSE_TZ = "Asia/Almaty";

type RawDay = {
  index: number;
  offset_days: number;
  weekday?: string;
  title: string;
  tasks?: string[];
  homework?: string | null;
  start_override?: string | null;
  hackathon?: boolean;
  blocks?: (string | { name?: string; span?: number } | null)[];
  duration_minutes?: number;
  block_step_minutes?: number;
  slot_starts_minutes?: number[];
};

type RawCourse = {
  shifts: Record<string, { label: string; start: string }>;
  days: RawDay[];
  lesson_minutes?: number;
  block_step_minutes: number;
  slot_starts_minutes?: number[];
};

export type CourseDay = {
  index: number;
  offsetDays: number;
  title: string;
  tasks: string[];
  /** Пустая строка в YAML («в таблице пусто») — домашки нет. */
  homework: string | null;
  startOverride: string | null;
  hackathon: boolean;
  durationMinutes: number;
};

const raw = parse(readFileSync(path.join(process.cwd(), "bot", "config", "course.yaml"), "utf8")) as RawCourse;

export const courseDaysList: CourseDay[] = raw.days
  .map((d) => ({
    index: Number(d.index),
    offsetDays: Number(d.offset_days),
    title: d.title,
    tasks: d.tasks ?? [],
    homework: d.homework?.trim() || null,
    startOverride: d.start_override ?? null,
    hackathon: !!d.hackathon,
    durationMinutes: lessonDurationMinutes(d)
  }))
  .sort((a, b) => a.index - b.index);

/** Mirrors bot/app/db.py:_lesson_duration_minutes. */
function lessonDurationMinutes(day: RawDay): number {
  if (day.duration_minutes) return Number(day.duration_minutes);
  const unevenSlots =
    !!day.slot_starts_minutes?.length || (!day.block_step_minutes && !!raw.slot_starts_minutes?.length);
  if (unevenSlots && raw.lesson_minutes) return Number(raw.lesson_minutes);
  const step = Number(day.block_step_minutes ?? raw.block_step_minutes);
  const slots = (day.blocks ?? []).reduce<number>(
    (n, b) => n + (b && typeof b === "object" ? Math.max(1, Number(b.span ?? 1)) : 1),
    0
  );
  return slots * step;
}

export function getCourseDay(index: number): CourseDay | undefined {
  return courseDaysList.find((d) => d.index === index);
}

export type GroupSchedule = { startDate: Date | null; lessonTime: string | null; shift: string };

/** Начало занятия: start_override дня → ручной lesson_time группы → время смены. */
export function lessonStart(group: GroupSchedule, day: CourseDay): Date | null {
  if (!group.startDate) return null;
  // @db.Date приходит из Prisma полуночью UTC — берём календарную дату как есть.
  const date = new Date(group.startDate);
  date.setUTCDate(date.getUTCDate() + day.offsetDays);
  const hm = day.startOverride ?? group.lessonTime ?? raw.shifts[group.shift || "evening"]?.start ?? "19:00";
  const [hh, mm] = hm.split(":").map(Number);
  return zonedTime(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate(), hh, mm);
}

/** Срок домашки — начало следующего занятия; у последнего дня срока нет. */
export function homeworkDue(group: GroupSchedule, day: CourseDay): Date | null {
  const next = courseDaysList.find((d) => d.index > day.index);
  return next ? lessonStart(group, next) : null;
}

/** «пн, 13.10 · 19:00» в часовом поясе курса. */
export function formatLesson(date: Date): string {
  const day = date.toLocaleDateString("ru-RU", { timeZone: COURSE_TZ, weekday: "short", day: "2-digit", month: "2-digit" });
  const time = date.toLocaleTimeString("ru-RU", { timeZone: COURSE_TZ, hour: "2-digit", minute: "2-digit" });
  return `${day} · ${time}`;
}

/** Тот же календарный день в часовом поясе курса. */
export function sameCourseDate(a: Date, b: Date): boolean {
  const fmt = (d: Date) => d.toLocaleDateString("en-CA", { timeZone: COURSE_TZ });
  return fmt(a) === fmt(b);
}

/** Wall-clock time in the course time zone → instant. month is 0-based, like Date.UTC. */
export function zonedTime(year: number, month: number, day: number, hh: number, mm: number): Date {
  const asUtc = Date.UTC(year, month, day, hh, mm);
  return new Date(asUtc - tzOffsetMs(new Date(asUtc)));
}

function tzOffsetMs(at: Date): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: COURSE_TZ,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  }).formatToParts(at);
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value);
  return Date.UTC(get("year"), get("month") - 1, get("day"), get("hour"), get("minute"), get("second")) - at.getTime();
}
