export type HomeworkStatus = "submitted" | "accepted" | "returned";

export const HOMEWORK_MAX_LENGTH = 5000;

export const homeworkStatusLabel: Record<HomeworkStatus, string> = {
  submitted: "на проверке",
  accepted: "принята",
  returned: "вернули на доработку"
};

export function isHomeworkStatus(value: unknown): value is HomeworkStatus {
  return value === "submitted" || value === "accepted" || value === "returned";
}
