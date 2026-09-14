import Image from "next/image";
import Link from "next/link";

/**
 * Minimal header for the workbook/mentor app shell — shares the marketing
 * site's navy/gold brand look (see app/globals.css, tailwind.config.ts) but
 * without the marketing nav, so it stays independent of components/marketing.
 */
export function AppHeader({ title, backHref, backLabel }: { title: string; backHref?: string; backLabel?: string }) {
  return (
    <header className="flex h-10 shrink-0 items-center gap-2 border-b border-white/10 bg-navy-950 px-3 text-white">
      <Image
        src="/prime-teens-logo.png"
        alt="PrimeTeens"
        width={22}
        height={22}
        className="h-[22px] w-[22px] shrink-0 rounded object-cover"
      />
      <span className="min-w-0 truncate font-display text-xs font-semibold text-porcelain sm:text-sm">{title}</span>
      {backHref && (
        <Link href={backHref} className="ml-auto shrink-0 whitespace-nowrap text-xs text-muted underline hover:text-champagne sm:text-sm">
          {backLabel ?? "Назад"}
        </Link>
      )}
    </header>
  );
}
