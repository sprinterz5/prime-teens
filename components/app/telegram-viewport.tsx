"use client";

import { useEffect } from "react";

type TelegramWebApp = {
  initData?: string;
  ready?: () => void;
  expand?: () => void;
  disableVerticalSwipes?: () => void;
};

/**
 * Inside a Telegram Mini App: open at full height instead of the half-screen
 * sheet, and stop a vertical swipe (scrolling the workbook, drawing with a
 * finger) from collapsing or closing the app. No-op in a normal browser.
 */
export function TelegramViewport() {
  useEffect(() => {
    function apply() {
      const app = (window as unknown as { Telegram?: { WebApp?: TelegramWebApp } }).Telegram?.WebApp;
      if (!app?.initData) return;
      app.ready?.();
      app.expand?.();
      app.disableVerticalSwipes?.();
    }

    if ((window as unknown as { Telegram?: unknown }).Telegram) {
      apply();
      return;
    }
    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-web-app.js";
    script.async = true;
    script.onload = apply;
    document.head.appendChild(script);
  }, []);

  return null;
}
