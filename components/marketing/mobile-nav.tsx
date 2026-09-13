"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { ArrowRight, Menu, X } from "lucide-react";
import { siteConfig } from "@/config/site";

export function MobileNav() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <div className="md:hidden">
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Открыть меню"
        aria-expanded={open}
        className="focus-ring inline-flex h-11 w-11 items-center justify-center rounded-lg border border-white/[0.12] text-porcelain"
      >
        <Menu size={20} aria-hidden="true" />
      </button>

      {open &&
        createPortal(
          <div className="fixed inset-0 z-50 bg-navy-950/98 backdrop-blur-xl">
            <div className="mx-auto flex h-20 w-full max-w-7xl items-center justify-between px-4 sm:px-6">
              <span className="font-display text-base font-semibold text-porcelain">{siteConfig.name}</span>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Закрыть меню"
                className="focus-ring inline-flex h-11 w-11 items-center justify-center rounded-lg border border-white/[0.12] text-porcelain"
              >
                <X size={20} aria-hidden="true" />
              </button>
            </div>

            <nav className="flex flex-col gap-2 px-4 py-8 sm:px-6" aria-label="Мобильное меню">
              {siteConfig.nav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className="focus-ring rounded-lg px-3 py-4 font-display text-2xl font-semibold text-porcelain transition hover:text-gold-300"
                >
                  {item.label}
                </Link>
              ))}

              <Link
                href="/#contact"
                onClick={() => setOpen(false)}
                className="btn btn-primary focus-ring mt-6 w-full"
              >
                Записаться
                <ArrowRight size={18} aria-hidden="true" />
              </Link>
            </nav>
          </div>,
          document.body
        )}
    </div>
  );
}
