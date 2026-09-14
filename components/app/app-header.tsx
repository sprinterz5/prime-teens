import Image from "next/image";
import Link from "next/link";

/**
 * Minimal header for the workbook/mentor app shell — shares the marketing
 * site's navy/gold brand look (see app/globals.css, tailwind.config.ts) but
 * without the marketing nav, so it stays independent of components/marketing.
 */
export function AppHeader({ title, backHref, backLabel }: { title: string; backHref?: string; backLabel?: string }) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-white/10 bg-navy-950 px-4 text-white">
      <Image
        src="/prime-teens-logo.png"
        alt="PrimeTeens"
        width={28}
        height={28}
        className="h-7 w-7 rounded object-cover"
      />
      <span className="font-display text-sm font-semibold text-porcelain">{title}</span>
      {backHref && (
        <Link href={backHref} className="ml-auto text-sm text-muted underline hover:text-champagne">
          {backLabel ?? "Назад"}
        </Link>
      )}
    </header>
  );
}
