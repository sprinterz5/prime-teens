"use client";

export function LogoutButton() {
  async function onClick() {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => null);
    window.location.replace("/login");
  }
  return (
    <button type="button" onClick={onClick} className="shrink-0 whitespace-nowrap text-xs text-muted underline hover:text-champagne sm:text-sm">
      Выйти
    </button>
  );
}
