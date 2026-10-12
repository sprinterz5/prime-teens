import { COURSE_TZ, courseDaysList, homeworkDue, lessonStart, type GroupSchedule } from "@/lib/course";

export type CalendarEvent = {
  uid: string;
  kind: "lesson" | "homework" | "deadline";
  title: string;
  start: Date;
  end: Date | null;
  allDay: boolean;
  href: string | null;
  deadlineId?: number;
  /** Homework already handed in. */
  done?: boolean;
};

type Deadline = { id: number; title: string; dueAt: Date; allDay: boolean };

/**
 * A student's calendar: lessons and homework deadlines computed from the
 * course program (same rules as the bots' reminders), plus the personal
 * deadlines they added themselves. Sorted by time.
 */
export function studentEvents(
  group: GroupSchedule,
  deadlines: Deadline[],
  submittedHomeworkDays: Set<number> = new Set()
): CalendarEvent[] {
  const events: CalendarEvent[] = [];
  for (const day of courseDaysList) {
    const start = lessonStart(group, day);
    if (!start) continue;
    events.push({
      uid: `lesson-${day.index}`,
      kind: "lesson",
      title: `День ${day.index}: ${day.title}`,
      start,
      end: new Date(start.getTime() + day.durationMinutes * 60_000),
      allDay: false,
      href: `/course/day/${day.index}`
    });
    const due = day.homework ? homeworkDue(group, day) : null;
    if (due && day.homework) {
      const done = submittedHomeworkDays.has(day.index);
      events.push({
        uid: `homework-${day.index}`,
        kind: "homework",
        title: done ? `✓ Домашка сдана: ${day.homework}` : `Сдать домашку: ${day.homework}`,
        start: due,
        end: null,
        allDay: false,
        href: `/course/day/${day.index}`,
        done
      });
    }
  }
  for (const d of deadlines) {
    events.push({
      uid: `deadline-${d.id}`,
      kind: "deadline",
      title: d.title,
      start: d.dueAt,
      end: null,
      allDay: d.allDay,
      href: null,
      deadlineId: d.id
    });
  }
  return events.sort((a, b) => a.start.getTime() - b.start.getTime());
}

/** YYYY-MM-DD of an instant in the course time zone. */
export function courseDateKey(date: Date): string {
  return date.toLocaleDateString("en-CA", { timeZone: COURSE_TZ });
}

function icsEscape(text: string): string {
  return text.replace(/\\/g, "\\\\").replace(/;/g, "\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");
}

function icsUtc(date: Date): string {
  return date.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
}

/** RFC 5545 lines are folded at 75 octets; continuation lines start with a space. */
function fold(line: string): string {
  const bytes = Buffer.from(line, "utf8");
  if (bytes.length <= 75) return line;
  const parts: string[] = [];
  let current = "";
  for (const ch of line) {
    if (Buffer.byteLength(current + ch, "utf8") > (parts.length ? 74 : 75)) {
      parts.push(current);
      current = "";
    }
    current += ch;
  }
  parts.push(current);
  return parts.join("\r\n ");
}

/** The student's calendar as an .ics feed (Google/Apple Calendar subscription). */
export function toIcs(events: CalendarEvent[], opts: { name: string; siteUrl: string; studentId: number }): string {
  const stamp = icsUtc(new Date());
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//PrimeTeens//Course calendar//RU",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    `X-WR-CALNAME:${icsEscape(opts.name)}`,
    `X-WR-TIMEZONE:${COURSE_TZ}`,
    "REFRESH-INTERVAL;VALUE=DURATION:PT6H"
  ];
  for (const e of events) {
    lines.push("BEGIN:VEVENT", `UID:${e.uid}-s${opts.studentId}@primeteens`, `DTSTAMP:${stamp}`);
    if (e.allDay) {
      const day = courseDateKey(e.start).replace(/-/g, "");
      lines.push(`DTSTART;VALUE=DATE:${day}`);
    } else {
      lines.push(`DTSTART:${icsUtc(e.start)}`);
      lines.push(`DTEND:${icsUtc(e.end ?? new Date(e.start.getTime() + 15 * 60_000))}`);
    }
    lines.push(`SUMMARY:${icsEscape(e.title)}`);
    if (e.href) lines.push(`URL:${opts.siteUrl}${e.href}`);
    if (e.kind !== "lesson" && !e.done) lines.push("BEGIN:VALARM", "ACTION:DISPLAY", `DESCRIPTION:${icsEscape(e.title)}`, "TRIGGER:-PT12H", "END:VALARM");
    lines.push("END:VEVENT");
  }
  lines.push("END:VCALENDAR");
  return lines.map(fold).join("\r\n") + "\r\n";
}
