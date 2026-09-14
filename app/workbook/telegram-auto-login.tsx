"use client";

import { useEffect } from "react";

declare global {
  interface Window {
    Telegram?: { WebApp?: { initData?: string } };
  }
}

const ATTEMPT_KEY = "wb_tg_auth_attempted";

/**
 * If this page is opened inside the Telegram client as a Mini App, Telegram
 * injects `window.Telegram.WebApp.initData`. We POST it once to
 * /api/auth/telegram (server verifies the HMAC signature, see
 * lib/auth/telegram.ts) and reload on success to pick up the session cookie.
 * A no-op in a normal browser tab (Telegram is undefined).
 */
export function TelegramAutoLogin() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (sessionStorage.getItem(ATTEMPT_KEY)) return;

    function tryAuth() {
      const initData = window.Telegram?.WebApp?.initData;
      if (!initData) return;
      sessionStorage.setItem(ATTEMPT_KEY, "1");
      fetch("/api/auth/telegram", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initData })
      }).then((res) => {
        if (res.ok) window.location.reload();
      });
    }

    if (window.Telegram?.WebApp) {
      tryAuth();
      return;
    }
    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-web-app.js";
    script.async = true;
    script.onload = tryAuth;
    document.head.appendChild(script);
  }, []);

  return null;
}
